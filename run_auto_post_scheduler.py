"""
Home Cartel - Automated Instagram Post Scheduler Worker
Monitors scheduled Stories, Reels, and Feeds and publishes them to Instagram at the exact Philippine Time (PHT).
"""

import os
import time
import requests
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

PHT = timezone(timedelta(hours=8))
CRON_SECRET = os.environ.get("CRON_SECRET", "")
API_URL = "http://localhost:3000/api/schedules/runner"

def get_pht_now_str():
    return datetime.now(PHT).strftime("%Y-%m-%d %I:%M:%S %p PHT")

def run_scheduler_tick():
    now_str = get_pht_now_str()
    try:
        headers = {"Authorization": f"Bearer {CRON_SECRET}"} if CRON_SECRET else {}
        res = requests.get(API_URL, headers=headers, timeout=30)
        if res.ok:
            data = res.json()
            results = data.get("results", [])
            published = [r for r in results if r.get("action") == "published"]
            pending = [r for r in results if r.get("action") == "pending_future"]
            errors = [r for r in results if r.get("action") == "error"]

            if published:
                print(f"\n=======================================================")
                print(f"[{now_str}] 🚀 PUBLISHED {len(published)} ITEM(S) TO INSTAGRAM!")
                for p in published:
                    print(f"  --> {p.get('category').upper()}: {p.get('idea')} (ID: {p.get('key')})")
                    details = p.get('details', {})
                    if details.get('id'):
                        print(f"      Instagram Post ID: {details.get('id')}")
                print(f"=======================================================\n")
            elif pending:
                next_item = sorted(pending, key=lambda x: x.get('timeDiffMinutes', 999999))[0]
                print(f"[{now_str}] Active: {len(pending)} scheduled. Next: {next_item.get('category')} '{next_item.get('idea')}' in {next_item.get('timeDiffMinutes')}m ({next_item.get('details')})")
            else:
                print(f"[{now_str}] Idle: No pending items to post at this time.")

            if errors:
                for err in errors:
                    print(f"  [!] Warning on {err.get('idea')}: {err.get('details')}")

        else:
            print(f"[{now_str}] Runner returned status {res.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"[{now_str}] Waiting for UI server on http://localhost:3000 to be online...")
    except Exception as e:
        print(f"[{now_str}] Scheduler check error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("  HOME CARTEL - INSTAGRAM AUTO-POST SCHEDULER")
    print("  Timezone: Philippine Standard Time (UTC+08:00)")
    print("=" * 60)
    print(f"Started at: {get_pht_now_str()}")

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_scheduler_tick()
    else:
        print("Polling schedule every 60 seconds... (Press Ctrl+C to stop)\n")
        while True:
            run_scheduler_tick()
            time.sleep(60)
