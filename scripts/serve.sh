#!/usr/bin/env bash
# Start the agent: app server + cloudflared tunnel + webhook registration.
#
# trycloudflare hostnames are ephemeral and the tunnel's control stream drops
# without warning. When that happens Telegram gets a 530 and the bot goes quiet
# with no error anywhere obvious - so this script always takes a fresh tunnel
# and re-registers, rather than assuming the old one still works.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=./venv/bin/python
LOG_DIR=/tmp

echo "==> stopping anything already running"
pkill -f "uvicorn app.main" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 2

echo "==> starting app server on :8000"
$PY -m uvicorn app.main:app --port 8000 --log-level info > $LOG_DIR/uvicorn.log 2>&1 &
for i in $(seq 1 20); do
  curl -sf --max-time 3 http://127.0.0.1:8000/healthz >/dev/null && break
  sleep 1
done
if ! curl -sf --max-time 3 http://127.0.0.1:8000/healthz >/dev/null; then
  echo "!! server failed to start. Last lines:"; tail -20 $LOG_DIR/uvicorn.log; exit 1
fi
echo "    server up"

# Some trycloudflare hostnames never get a DNS record published. Retrying
# setWebhook against one of those can never succeed - it needs a NEW tunnel.
# So: verify the hostname actually resolves publicly, and rotate if it doesn't.
register() {
  local url="$1" host="${1#https://}"
  for i in $(seq 1 10); do
    if dig +short "$host" @1.1.1.1 | grep -qE '^[0-9]'; then
      if $PY scripts/set_webhook.py "$url" 2>&1 | grep -q "setWebhook OK"; then
        return 0
      fi
    fi
    sleep 6
  done
  return 1
}

for attempt in 1 2 3 4; do
  echo "==> starting tunnel (attempt $attempt)"
  pkill -f "cloudflared tunnel" 2>/dev/null; sleep 2
  : > $LOG_DIR/cloudflared.log
  ~/.local/bin/cloudflared tunnel --url http://localhost:8000 > $LOG_DIR/cloudflared.log 2>&1 &

  URL=""
  for i in $(seq 1 30); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' $LOG_DIR/cloudflared.log | head -1)
    [ -n "$URL" ] && break
    sleep 2
  done
  if [ -z "$URL" ]; then
    echo "    no URL from cloudflared, retrying"
    continue
  fi
  echo "    tunnel: $URL"

  echo "==> registering webhook"
  if register "$URL"; then
    echo "$URL" > $LOG_DIR/tunnel_url.txt
    echo "    registered"
    $PY scripts/check_bot.py
    echo
    echo "READY. Test link:"
    $PY - <<'EOF'
import sys; sys.path.insert(0, ".")
import httpx
from app.config import load
s = load()
r = httpx.get(s.supabase_url + "/rest/v1/deep_link_tokens",
              params={"lead_id": "eq.LEAD-001", "select": "token"},
              headers={"apikey": s.supabase_service_role_key,
                       "Authorization": "Bearer " + s.supabase_service_role_key})
print("  https://t.me/Estateagent39_bot?start=" + r.json()[0]["token"])
EOF
    exit 0
  fi
  echo "    that hostname never resolved - rotating to a new tunnel"
done

echo "!! could not register the webhook. The tunnel hostname may be bad - re-run this script."
exit 1
