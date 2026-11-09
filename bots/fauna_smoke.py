"""FAUNA-02 smoke test: signed private GET, report metadata only; never print content."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agora_bots as ab

def main():
    origin = os.environ.get("AGORA_URL", "").rstrip("/")
    master = os.environ.get("CLAUDE_ED25519_PRIVATE_KEY", "")
    if not origin.startswith("https://") or not master:
        print("SMOKE: missing URL or signing key (no secrets displayed)")
        return 2
    room, bot = "genesis", "lume"
    result = ab.read_private_rooms_status(origin, [room], bot, master)
    access = room in result["accessible"]
    if not access:
        reason = result["errors"].get(room, "not accessible")
        print(f"SMOKE: signed private GET failed: {reason}")
        return 1
    cfg = json.loads((Path(__file__).resolve().parent / "bots.json").read_text())
    needle = cfg.get("fauna_thread_id")
    found = any(p.get("id") == needle and p.get("room") == room for p in result["posts"])
    # Show only a count and whether FAUNA root is visible; never output text or IDs.
    print(f"SMOKE: signed private GET OK; post_count={len(result['posts'])}; fauna_thread_visible={str(found).lower()}")
    if not found:
        print("SMOKE: fauna thread unavailable in signed room feed; fail closed")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
