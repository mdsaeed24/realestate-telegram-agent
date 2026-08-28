# BUILD_SPEC — realestate-telegram-agent

Derived from [project_brief.md](project_brief.md) (behaviour, source of truth), [CLAUDE.md](CLAUDE.md)
(architecture + silent-failure constraints), and a live inspection of the Supabase project
`qadbtaretnzzrizoaynb` over MCP on 2026-08-28.

---

## 0. Ground truth as of writing

**Storage.** Bucket `Property media` (public). One folder:

```
Property media/Sobha Magnolia/
  Hero.png      725,718 B
  Image 1.png   393,880 B
  Image 2.png 1,472,847 B
  Image3.png  1,464,295 B
```

Four files, PNG, **not** the `hero.jpg` / `image1..4.jpg` the build prompt assumed. Naming is
inconsistent (space before the digit in two of three; capital `H`). **No video file exists anywhere
in the bucket.** Filenames are therefore never derived — they are read from the sheet (§2).

**Location.** The brief says Bengaluru; CLAUDE.md says Gurgaon. Brief wins. CLAUDE.md's `projectbrief.md`
reference is also stale — the file is `project_brief.md`. Both corrected in Phase 1.

**Decided upstream, not reopened:** bucket stays public; only one property has media, and a listing
without media is normal behaviour (text details + "photos aren't up for this one yet"), not an error;
`media_folder` is its own sheet field so adding media later is a data change, not a code change.

---

## 1. Decisions taken in the interview

| Area | Decision |
|---|---|
| First contact | Telegram bots cannot DM first. Each lead gets `t.me/<bot>?start=<token>`; the business sends that link over its existing channel. `/start` resolves the token → lead row → greeting by name. |
| Lead identity | `lead_id`, a stable column in the Leads sheet the client never edits. Supabase state and deep-link tokens key off it. `chat_id` is recorded on first contact. |
| Media mapping | Explicit sheet columns: `media_folder`, `hero_file`, `gallery_files`, `video_file`. |
| Video | Fully specced with the ffprobe gate; treated as absent (silently skipped) until a file exists. |
| Gone quiet | One nudge at ~24h referencing where they left off. No reply → parked forever. |
| Return visit | Restore state, re-confirm the stored requirement in one line, then continue. |
| Language | Detect once from the first substantive message, store on the lead, hold for the conversation. Switch only on a clear sustained change — code-mixing must not cause flip-flopping. |
| State | Supabase holds stage, slots, chosen property, media-sent log, `file_id` cache, bookings, full transcript. Property rows are read live from Sheets so client edits take effect immediately. |
| No matches | Say so plainly, then offer nearest real alternatives. Never widen silently. |
| Unknown property | Fuzzy-match against the shown list, confirm in one line. No match → say we don't have it, re-show the list. Never invent a property. |
| Slot conflict | Overlapping bookings are allowed and recorded; the sales team reconciles. See the tradeoff note in §7. |
| Duplicate webhooks | `update_id` inserted into a Postgres table with a unique constraint before any work begins. |
| Media delivery | First send passes the public Supabase URL; cache the returned `file_id`; on a stale-identifier failure, re-send by URL and overwrite the cache. |
| Gallery | Hero alone first. On consent, the remaining three go as one media group. |
| Sheet tabs | Properties, Leads, Bookings. |
| Model | **Deferred — you will name it.** Held in one place (`ANTHROPIC_MODEL` in config) so switching is a config change, not a code change. See Phase 5. |

---

## 2. Data model

### Google Sheet (client-editable, created and seeded in Phase 2)

**Properties**

| Column | Notes |
|---|---|
| `property_id` | stable, e.g. `PROP-001` |
| `name` | `Sobha Magnolia` |
| `property_type` | `2BHK` / `3BHK` / `Villa` / `Plot` |
| `price_inr` | integer rupees; matching is numeric, never string |
| `locality`, `city` | `Bengaluru-Mysuru Expressway`, `Bengaluru` |
| `status` | `active` / `hidden` — only `active` is ever shown |
| `key_details` | newline-separated bullets, sent verbatim |
| `maps_url` | sent on booking confirmation |
| `media_folder` | `Sobha Magnolia` — blank means no media |
| `hero_file` | `Hero.png` |
| `gallery_files` | `Image 1.png\|Image 2.png\|Image3.png` (pipe-separated, order preserved) |
| `video_file` | blank today |

**Leads**: `lead_id`, `name`, `phone`, `source`, `enquired_about`, `status`, `deep_link`.
`deep_link` is written back by the seeding script. `status` ∈ `new` / `engaged` / `qualified` /
`booked` / `not_looking` / `parked`.

**Bookings** (agent-written mirror; Supabase is the system of record): `booking_id`, `lead_id`,
`lead_name`, `property_id`, `property_name`, `slot_date`, `slot_time`, `maps_url`, `created_at`.

### Supabase (created via MCP in Phase 1)

- `leads_state` — `lead_id` PK, `chat_id` unique, `stage`, `language`, `slots` jsonb
  (`{type, budget_min, budget_max, area}`), `shown_property_ids` int[], `selected_property_id`,
  `opted_out` bool, `last_inbound_at`, `nudged_at`, `updated_at`
- `messages` — full transcript: `lead_id`, `direction`, `text`, `telegram_message_id`, `created_at`
- `processed_updates` — `update_id` bigint **PK** (this is the idempotency gate), `received_at`
- `media_cache` — `property_id`, `file_key`, `kind` (`photo`/`video`), `telegram_file_id`,
  unique on `(property_id, file_key)`
- `media_sent` — `(lead_id, property_id, file_key)` unique; prevents a redelivered update resending photos
- `bookings` — `lead_id`, `property_id`, `slot_start`, `slot_end`, `status`, `created_at`. **No**
  uniqueness on `(property_id, slot_start)`, per the decision above
- `deep_link_tokens` — `token` PK, `lead_id`, `created_at`, `used_at`

---

## 3. Module layout

```
app/
  config.py            env loading; fails loudly on a missing required var
  main.py              FastAPI app; POST /webhook/telegram; GET /healthz
  telegram/
    client.py          send_message, send_photo, send_media_group, send_video, get_file
    webhook.py         secret-token check, update parsing, ack-then-process
  sheets/
    client.py          service-account auth
    properties.py      read Properties -> Property dataclass
    leads.py           read/write Leads
    bookings.py        append to Bookings
  store/               Supabase reads/writes, one module per table above
  domain/
    stages.py          the stage machine; the only place stage transitions happen
    matching.py        deterministic filtering and ranking
    slots.py           normalisation ("2 cr", "two crore", "20000000" -> 20_000_000)
    resolve.py         fuzzy match of a reply to a shown listing
  llm/
    client.py          Anthropic client
    extract.py         intent + slot extraction (structured outputs)
    compose.py         reply drafting in the lead's language
    language.py        detection
  media/
    sender.py          hero -> album -> video, file_id cache + URL fallback
    probe.py           ffprobe validation
  jobs/
    nudge.py           the 24h sweeper
tests/
```

**The architecture rule, concretely:** `domain/` never imports `llm/`. `llm/extract.py` returns a
typed intent + slots; `domain/` decides stage, matches properties, and decides what to send;
`llm/compose.py` is handed the decided content and only chooses wording. `media/sender.py` is called
by `domain/`, sends bytes/URLs directly to Telegram, and never returns a URL to the model.

---

## 4. Conversation stages

`NEW → GREETED → QUALIFYING → LISTED → PROPERTY_SELECTED → MEDIA_OFFERED → BOOKING → CONFIRMED`,
plus terminal `NOT_LOOKING` and `PARKED`.

Every inbound message: dedupe on `update_id` → load state → extract intent/slots (LLM) → `domain/`
decides the transition and the payload → compose wording (LLM) → send → persist state + transcript.

`NOT_LOOKING` is absorbing: the agent never messages that lead again, and the nudge job skips
`opted_out`.

---

## 5. Out of scope

Payments; CRM integration; inbound calls; agent-initiated broadcast of any kind; a web dashboard;
multi-bot or multi-tenant support; lead scoring; automated slot availability from a real calendar
(bookings are recorded, not scheduled against availability).

---

## 6. Phases

Each phase ends with a command you can run that proves it works. Do not start a phase until the
previous verification passes. `.env.example` gains that phase's variables at the start of the phase,
grouped under a comment heading — not all at once up front.

### Phase 0 — Tooling preflight
Install `ffmpeg` (provides `ffprobe`) and `cloudflared`; both are currently absent. Fix CLAUDE.md's
Gurgaon → Bengaluru and `projectbrief.md` → `project_brief.md`.
**Verify:** `ffprobe -version && cloudflared --version` both print a version.

### Phase 1 — Config + Supabase schema
`app/config.py`; all tables in §2 created via MCP `apply_migration`.
**Env added:** `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`.
**Verify:** `list_tables` over MCP shows all seven tables with the stated constraints; `pytest tests/test_config.py` passes.

### Phase 2 — Google Sheet created and seeded
I create the sheet from the service account, add the three tabs and headers, seed five properties
(Sobha Magnolia with the real filenames above; four with `media_folder` blank), seed test leads, and
write `deep_link` back per lead.
**Env added:** `GOOGLE_SHEET_ID`, `GOOGLE_CREDENTIALS_PATH`.
**Blocked on you:** `credentials.json` in the project root, and the service account email shared on the sheet.
**Verify:** `python -m scripts.dump_sheet` prints all five properties and the seeded leads read back through the API.

### Phase 3 — Webhook skeleton + idempotency
FastAPI app, secret-token check, immediate 200 ack, background processing, `processed_updates` gate.
**Env added:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `PUBLIC_BASE_URL`.
**Verify:** POST the same update twice with curl → one row in `processed_updates`, one reply sent, second returns 200 without side effects. `getWebhookInfo` shows zero pending errors.

### Phase 4 — Deep link, greeting, qualification
`/start <token>` resolves to a lead, greets by name, asks type/budget/area; "no" ends gracefully into `NOT_LOOKING`.
**Verify:** end-to-end in a real Telegram chat from a seeded deep link; `leads_state` shows populated slots; the "no" path leaves `opted_out = true`.

### Phase 5 — LLM layer
Adaptive thinking, structured outputs for extraction. Language detected once and held.

**Model is deferred.** The id lives in `ANTHROPIC_MODEL` (env, read once in `app/config.py`) and is
referenced nowhere else, so naming it later is a one-line change. Until you choose, write the calling
code against the baseline that holds across every current Claude model, so no rewrite is needed:

- **No assistant prefill.** Removed across the current family — control output shape with
  `output_config.format` or the system prompt, never a prefilled assistant turn.
- **Operator context goes in the top-level `system` field**, cached. Mid-conversation `role: "system"`
  messages exist only on some models; avoiding them keeps the code portable.
- **`thinking: {"type": "adaptive"}`**, with depth tuned via `output_config.effort` rather than
  `budget_tokens` (removed on current models).

The one thing that genuinely varies by choice is cost per turn, which matters here because every
inbound message costs two calls (extract + compose). Worth weighing when you pick.

**Env added:** `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`.
**Verify:** `pytest tests/test_extract.py` over a fixture set of Hindi / Kannada / Tamil / Konkani / Hinglish messages; a code-mixed message must not flip the stored language.

### Phase 6 — Matching + listing
Numeric budget matching, area matching, five results max, numbered list with prices. No-match path
offers nearest alternatives.
**Verify:** `pytest tests/test_matching.py` — includes the 50L-in-Koramangala case asserting the honest no-match reply, and asserts hidden properties never appear.

### Phase 7 — Media
Hero by public URL → cache `file_id` → consent → remaining three as one media group. Stale `file_id`
falls back to URL and overwrites the cache. `media_sent` prevents double-sends. A property with a
blank `media_folder` sends text details and says photos aren't up yet.
**Gate before this phase runs:** if `video_file` is non-blank, `ffprobe` must confirm H.264 video,
AAC audio, and exactly one audio stream. A file failing any of these uploads fine and then silently
fails to play — the phase does not pass on a 200 from `sendVideo`.
**Verify:** send to a real chat; then re-send to a second chat and show from the logs that the second
used the cached `file_id`; then corrupt the cached `file_id` in Supabase and show the send still
succeeds via URL fallback with the cache refreshed.

### Phase 8 — Booking
Capture date/time preference, write to Supabase, mirror to the Bookings tab, confirm with the maps link.
**Verify:** two leads booking the same slot both succeed and both appear in Supabase and the sheet.

### Phase 9 — Nudge job
Sweeper finds `last_inbound_at` older than 24h in a non-terminal stage with `nudged_at` null, sends
one contextual follow-up, stamps `nudged_at`. Never touches `opted_out` or terminal stages.
**Verify:** back-date a test lead's `last_inbound_at`, run the job twice, show exactly one nudge sent.

### Phase 10 — End-to-end
cloudflared tunnel up, webhook registered, full brief walkthrough in a real chat.
**Verify:** transcript in Supabase covering greeting → qualification → listing → selection → hero →
consent → album → booking → maps link, plus the no-media property answering honestly.

---

## 7. Tradeoffs worth revisiting

**Overlapping bookings.** The chosen design records both bookings and leaves reconciliation to the
sales team. The brief says a site visit is confirmed only once properly recorded — recording is what
the agent guarantees, so the confirmation wording should promise exactly that and no more.
Phase 8 will word it as a recorded, confirmed booking with the maps link; if you want it hedged
("the team will confirm the slot"), say so at Phase 8 and it's a one-line change.

**Sheets read live.** Client edits apply instantly, at the cost of a Sheets API call per listing
turn. If quota becomes a problem, add a short TTL cache in `sheets/properties.py` — deliberately not
built now.
