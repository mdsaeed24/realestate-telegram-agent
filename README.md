# Real Estate Telegram Agent

A conversational agent that qualifies real estate leads on Telegram, shows them
matching properties, sends photos on request, and books site visits — in English,
Hindi, Kannada, Tamil or Konkani.

Built for a Bengaluru property business whose leads arrive from web forms, social
channels and referrals, and who wanted a real conversation rather than a menu of
buttons.

## Architecture

**Deterministic Python owns all logic. The LLM only handles language.**

The model reads an inbound message into a typed intent, and separately words the
reply. Everything between those two steps — which stage the conversation is in,
which properties match, whether a booking is real — is decided by Python. The
stage machine (`app/domain/stages.py`) is pure: it takes state plus an extraction
and returns a plan, performing no I/O and never calling the model. That is what
makes the conversation testable.

```
Telegram ──> webhook ──> claim update_id ──> extract intent (LLM)
                                                    │
                                          stage machine decides (pure Python)
                                                    │
                                    compose wording (LLM) ──> send ──> persist
```

| Layer | Holds |
|---|---|
| Google Sheets | Properties and leads — the client edits these directly, read live |
| Supabase | Conversation state, transcripts, sessions, media cache, bookings |
| Supabase Storage | Property photos, served to Telegram by public URL |

## What it handles

- **Identity before attribution.** Deep links say who we *expect*, never who is
  actually there. Every conversation asks who is speaking; a name that doesn't
  match the link becomes a new lead rather than inheriting someone else's record.
- **Media with consent.** Hero photo alone first, the rest of the album only if
  asked. A property with no photos says so and offers a site visit instead —
  normal behaviour, not an error path.
- **Honest matching.** Nothing matching the budget or area is said plainly, with
  the nearest real alternatives offered. It never invents a property or a price.
- **One follow-up, ever.** A lead who goes quiet gets a single nudge, then is
  parked. Opted-out leads are never messaged again.
- **Language held, not flipped.** Detected once and kept; code-mixing
  ("2 BHK chahiye Whitefield mein") does not flip the conversation mid-flow.

## Failure modes designed around

These cause silent failures — the send returns 200 and the recipient gets nothing:

- **Duplicate delivery.** Telegram redelivers when an ack is slow. Every
  `update_id` is claimed via a Postgres primary key before work begins, so
  redelivery is a no-op across restarts and concurrent workers — not a set in
  process memory that a restart would lose.
- **Stale `file_id`.** Cached ids are reused across leads to avoid re-uploading,
  but they expire with no guarantee. A stale-id failure falls back to the public
  URL and refreshes the cache, rather than retrying a dead id.
- **Unsupported media.** Telegram rejects AVIF outright. Formats are verified by
  actually sending, not by trusting the file extension.
- **Video encoding.** An ffprobe gate checks H.264 + AAC + a single audio stream
  before a video is sent, because a non-conforming file uploads fine and then
  fails to play inline.

## Tests

```bash
python -m pytest tests/ -q     # 132 tests
```

Coverage is weighted toward the rules that matter: budget parsing across
languages, the no-match path, media consent, one-nudge-only, and the identity
boundary. Several tests are regressions from bugs that only appeared when running
real conversations end to end — a listing renumbered so "1" selected the wrong
property, and a confirmed booking that fell through to re-pitching.

## Running it

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env          # fill in the values
./scripts/serve.sh            # server + tunnel + webhook registration
```

`scripts/serve.sh` verifies the tunnel hostname actually resolves before
registering it, and rotates to a fresh tunnel if it does not — quick tunnels
sometimes come up with no DNS record at all.

## Stack

Python · FastAPI · Anthropic Claude API · Supabase (Postgres + Storage) ·
Google Sheets API · Telegram Bot API · httpx · pytest · ffmpeg
