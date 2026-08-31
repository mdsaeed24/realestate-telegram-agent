"""Sending property media.

Media goes straight to the lead - never a URL handed back to the model, because
the model cannot guarantee ordering and out-of-order media breaks the flow.

First send passes the public Supabase URL; the file_id Telegram returns is
cached and reused for every later lead. A stale file_id falls back to the URL
and refreshes the cache rather than retrying the dead id.
"""
import logging
import urllib.parse

from app.sheets.properties import Property
from app.store import media_cache
from app.store.client import Store
from app.telegram.client import Telegram, TelegramError

log = logging.getLogger("agent.media")

BUCKET = "Property media"


def public_url(supabase_url: str, folder: str, filename: str) -> str:
    path = urllib.parse.quote(f"{BUCKET}/{folder}/{filename}")
    return f"{supabase_url}/storage/v1/object/public/{path}"


async def _send_with_cache(
    tg: Telegram, store: Store, *, chat_id: int, prop: Property,
    file_key: str, url: str, kind: str, caption: str | None = None,
) -> str | None:
    """Send one file, preferring the cached file_id. Returns the fresh file_id."""
    send = tg.send_photo if kind == "photo" else tg.send_video
    cached = await media_cache.get(store, prop.property_id, file_key)

    if cached:
        try:
            result = await send(chat_id, cached, caption)
            return _extract_file_id(result, kind)
        except TelegramError as e:
            if not e.is_stale_file_id:
                raise
            log.warning("stale file_id for %s/%s, re-sending by URL",
                        prop.property_id, file_key)

    result = await send(chat_id, url, caption)
    file_id = _extract_file_id(result, kind)
    if file_id:
        await media_cache.put(store, prop.property_id, file_key, kind, file_id)
    return file_id


def _extract_file_id(result: dict, kind: str) -> str | None:
    if kind == "photo":
        photos = result.get("photo") or []
        return photos[-1]["file_id"] if photos else None
    video = result.get("video") or {}
    return video.get("file_id")


async def send_hero(tg: Telegram, store: Store, supabase_url: str, chat_id: int,
                    lead_id: str, prop: Property, caption: str | None = None) -> bool:
    """Send the hero image alone. Returns False when the property has no media."""
    if not prop.has_media:
        return False
    if await media_cache.already_sent(store, lead_id, prop.property_id, prop.hero_file):
        log.info("hero already sent to %s for %s", lead_id, prop.property_id)
        return True

    url = public_url(supabase_url, prop.media_folder, prop.hero_file)
    await _send_with_cache(tg, store, chat_id=chat_id, prop=prop,
                           file_key=prop.hero_file, url=url, kind="photo", caption=caption)
    await media_cache.mark_sent(store, lead_id, prop.property_id, prop.hero_file)
    return True


async def send_gallery(tg: Telegram, store: Store, supabase_url: str, chat_id: int,
                       lead_id: str, prop: Property) -> int:
    """Send the remaining photos as one album - they already consented, so
    drip-feeding further would be padding."""
    pending = [
        f for f in prop.gallery_files
        if not await media_cache.already_sent(store, lead_id, prop.property_id, f)
    ] if prop.gallery_files else []
    if not pending:
        return 0

    media = [
        {"type": "photo",
         "media": await media_cache.get(store, prop.property_id, f)
         or public_url(supabase_url, prop.media_folder, f)}
        for f in pending
    ]
    try:
        results = await tg.send_media_group(chat_id, media)
    except TelegramError as e:
        if not e.is_stale_file_id:
            raise
        log.warning("stale file_id in album for %s, re-sending all by URL", prop.property_id)
        media = [{"type": "photo",
                  "media": public_url(supabase_url, prop.media_folder, f)} for f in pending]
        results = await tg.send_media_group(chat_id, media)

    for filename, result in zip(pending, results):
        file_id = _extract_file_id(result, "photo")
        if file_id:
            await media_cache.put(store, prop.property_id, filename, "photo", file_id)
        await media_cache.mark_sent(store, lead_id, prop.property_id, filename)
    return len(pending)


async def send_video(tg: Telegram, store: Store, supabase_url: str, chat_id: int,
                     lead_id: str, prop: Property) -> bool:
    if not prop.has_video:
        return False
    url = public_url(supabase_url, prop.media_folder, prop.video_file)
    await _send_with_cache(tg, store, chat_id=chat_id, prop=prop,
                           file_key=prop.video_file, url=url, kind="video")
    await media_cache.mark_sent(store, lead_id, prop.property_id, prop.video_file)
    return True
