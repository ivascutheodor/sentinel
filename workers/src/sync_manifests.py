"""Sends every clip whose manifest says "synced": false to the backend.

Use it when the backend was down or unreachable while the worker recorded. Run from
workers/src (it uses the same workers/.env as monitor.py):

    python sync_manifests.py

Safe to run any number of times, also while monitor.py is running: an event the backend
already has is only marked as synced, never stored twice. Exits with 1 if anything is
still unsynced, so a scheduled task can report it.
"""

import sys

from config import settings
from manifest import MANIFESTS_DIR, find_unsynced, sync_manifest


def main() -> int:
    manifests_dir = settings.clips_dir / MANIFESTS_DIR
    pending = list(find_unsynced(manifests_dir))
    if not pending:
        print(f"[SYNC] Nothing to sync in {manifests_dir}.")
        return 0

    print(f"[SYNC] {len(pending)} manifest(s) not synced yet; sending to {settings.api_url}")
    failed = 0
    for path in pending:
        try:
            result = sync_manifest(path, settings.api_url, settings.api_key)
        except (OSError, ValueError, KeyError) as e:  # unreadable or incomplete manifest
            print(f"[SYNC] {path.name}: cannot read manifest ({type(e).__name__}: {e})")
            failed += 1
            continue
        print(f"[SYNC] {path.name}: {result.message}")
        failed += not result.synced

    print(f"[SYNC] Done: {len(pending) - failed} synced, {failed} still pending.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
