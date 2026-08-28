# CLAUDE.md

Standing rules for this project. For the product spec, lead qualification flow, property data model, and conversation design, see **projectbrief.md** — read it before starting work in a new session.

## What This Is

A Telegram agent that handles lead enquiries for a real estate firm in Gurgaon. Leads live in Google Sheets. The agent messages a lead, qualifies them on property type, budget, and location, shows matching properties, sends photos/video for a chosen property, understands multiple languages, and sends a reminder when a site visit is booked.

## Architecture Rule (Non-Negotiable)

Deterministic Python owns all logic, filtering, matching, and state. The LLM only handles conversation, intent parsing, and message wording. Never let the LLM decide business logic (qualification pass/fail, which properties match, what state the lead is in) — it drafts language and extracts intent, Python decides everything else.

Any tool that sends media (photos, video) must send it directly to the user, not return a URL to the model. The model cannot guarantee message ordering, and out-of-order media/text breaks the conversation.

## Data & Storage

All data and media lives in Supabase. No local SQLite, no local file storage, no in-memory-only state. If a session needs to survive a restart or be inspected later, it belongs in Supabase.

## Hard-Won Constraints (Cause Silent Failures)

- **Video format:** Telegram video must be MP4 container, H.264 video, AAC audio, single audio stream, with the `moov` atom at the start of the file (faststart). Files that don't meet this send but fail to preview inline or fail to stream — this fails silently, always verify by fetching the file back and checking its playability, not just checking the send API returned 200.
- **`file_id` is not permanent:** After uploading media to Telegram, cache the returned `file_id` in Supabase to avoid re-uploading. But `file_id` is bot-specific and can become invalid over time (Telegram gives no expiry guarantee). Always handle a failed send (e.g. "wrong file identifier") by re-uploading from the source file and refreshing the cached `file_id`, not by retrying the same one.
- **`file_path` is temporary — never cache it:** `getFile` returns a `file_path` used to *download* a file; it expires (~1 hour) and must never be persisted or reused for later downloads. Only `file_id` is cacheable.
- **Webhook vs. polling conflict:** Telegram allows only one active update-fetching mode per bot. If `setWebhook` is set while something else is also polling `getUpdates` (a stray local process, a second instance), Telegram returns 409 Conflict and messages silently stop arriving. Before debugging "the bot isn't responding," check for a 409 in the logs and confirm nothing else is polling the same token.
- **Webhook must ack fast:** Respond 200 to Telegram's webhook POST immediately, then process the message asynchronously. A slow handler causes Telegram to consider the delivery failed and it will redeliver, which can double-process a message if you're not idempotent.
- **Setting the webhook is one call, but don't skip it:** `setWebhook` (with your HTTPS URL) must be called explicitly — it is not a side effect of anything else. If you switch between webhook and local polling during development, remember to `deleteWebhook` before polling, and re-`setWebhook` before going back to webhook mode.

## Workflow Rules

- Claude Code must verify its own work and show evidence — test output, query results, an actual re-fetched file, a real API response — never assert something succeeded without showing the proof.
- The Supabase MCP is connected. Claude Code creates and verifies database schema itself directly through it; it does not hand the user raw SQL to paste in.
- Secrets live in `.env` only. Never commit `.env`, never print secret values (bot token, Supabase keys) to logs, terminal output, or commit messages.

## Running Locally

```bash
# Start the bot server
python -m app.main
# or, if using a framework entrypoint:
uvicorn app.main:app --reload --port 8000
```

```bash
# Expose the local server for Telegram's webhook (pick one tunnel tool)
ngrok http 8000
# or
cloudflared tunnel --url http://localhost:8000
```

```bash
# Register the webhook with Telegram (run once per tunnel URL change)
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://<your-tunnel-domain>/webhook/telegram" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

```bash
# If switching to local polling for quick dev iteration, remove the webhook first
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"
```

```bash
# Sanity check: confirm the webhook is actually set and see recent delivery errors
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```
