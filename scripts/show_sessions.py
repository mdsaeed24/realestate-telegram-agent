"""List recorded conversation sessions - who turned up, and what came of it."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.config import load  # noqa: E402

MARK = {"matched": "= expected lead", "different": "! different person",
        "unknown": "? no link"}


def main() -> int:
    s = load()
    h = {"apikey": s.supabase_service_role_key,
         "Authorization": f"Bearer {s.supabase_service_role_key}"}
    rows = httpx.get(f"{s.supabase_url}/rest/v1/sessions",
                     params={"select": "*", "order": "started_at.desc", "limit": "25"},
                     headers=h, timeout=30).json()
    if not rows:
        print("no sessions recorded yet")
        return 0

    print(f"{'session':<14} {'started':<17} {'name':<16} {'phone':<15} "
          f"{'lead':<12} {'outcome':<18} identity")
    print("-" * 110)
    for r in rows:
        msgs = httpx.get(f"{s.supabase_url}/rest/v1/messages",
                         params={"session_ref": f"eq.{r['session_ref']}",
                                 "select": "id"}, headers=h, timeout=30).json()
        print(f"{r['session_ref']:<14} {r['started_at'][:16]:<17} "
              f"{(r.get('claimed_name') or '-'):<16} {(r.get('claimed_phone') or '-'):<15} "
              f"{(r.get('lead_id') or '-'):<12} {(r.get('outcome') or '-'):<18} "
              f"{MARK.get(r.get('identity_match'), '-')}  ({len(msgs)} msgs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
