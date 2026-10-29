"""Manifest files: a sealed JSON record next to each clip, and the outbox for the backend.

recordings/
├── incident_2026-10-28_14-03-07.mp4
└── manifests/
    └── incident_2026-10-28_14-03-07.json   <- "synced": false until the backend has it

The manifest is written before the event is posted, so an event that never reached the
backend (API down, network error) can be sent later by sync_manifests.py.
"""

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

import requests

from recorder import Incident

MANIFESTS_DIR = "manifests"
SCHEMA_VERSION = 1


def sha256_of(path: Path) -> str:
    """SHA-256 of a file, read in 1 MB chunks so large clips don't fill the memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path_for(clip: Path) -> Path:
    return clip.parent / MANIFESTS_DIR / f"{clip.stem}.json"


def manifest_ref(path: Path) -> str:
    """The relative key the backend stores in `video_clips.source_manifest_ref`."""
    return f"{MANIFESTS_DIR}/{path.name}"


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Writes atomically: a crash leaves either the old file or the new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # a rename within one folder is atomic


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(
    incident: Incident,
    camera_id: str,
    config_snapshot: dict[str, Any],
    fps: int,
    frame_size: tuple[int, int],
) -> Path:
    """Seals the facts about a finished clip. Call after the video writer was released."""
    clip = incident.clip
    exists = clip.is_file()
    width, height = frame_size
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "synced": False,  # set to True once the backend has stored the event
        "camera_id": camera_id,
        "video": {
            "file": clip.name,
            "size_bytes": clip.stat().st_size if exists else 0,
            "sha256": sha256_of(clip) if exists else None,
            "codec": "h264",
            "fps": fps,
            "width": width,
            "height": height,
            "frame_count": incident.frame_count,
        },
        "started_at": incident.started_at.isoformat(),
        "last_person_seen_at": incident.last_person_seen_at.isoformat(),
        "closed_at": incident.closed_at.isoformat(),
        "end_reason": incident.end_reason,
        "recorded_start_at": incident.recorded_start_at.isoformat(),
        "recorded_end_at": incident.recorded_end_at.isoformat(),
        "config_snapshot": config_snapshot,
        "created_at": datetime.now(UTC).isoformat(),
    }
    path = manifest_path_for(clip)
    save_manifest(path, manifest)
    return path


def event_payload(manifest: dict[str, Any], ref: str) -> dict[str, Any]:
    """The POST /events body, built only from the manifest."""
    video = manifest["video"]
    payload = {
        "camera_id": manifest["camera_id"],
        "video_path": video["file"],
        "started_at": manifest["started_at"],
        "last_person_seen_at": manifest["last_person_seen_at"],
        "closed_at": manifest["closed_at"],
        "end_reason": manifest["end_reason"],
        "config_snapshot": manifest["config_snapshot"],
    }
    # Only a real, complete file can be verified; otherwise the backend keeps the clip
    # `pending` and stores no manifest reference.
    has_span = manifest["recorded_end_at"] > manifest["recorded_start_at"]
    if video["size_bytes"] > 0 and video["sha256"] and has_span:
        payload["size_bytes"] = video["size_bytes"]
        payload["recorded_start_at"] = manifest["recorded_start_at"]
        payload["recorded_end_at"] = manifest["recorded_end_at"]
        payload["source_manifest_ref"] = ref
    return payload


class SyncResult(NamedTuple):
    synced: bool
    message: str


def sync_manifest(
    path: Path,
    api_url: str,
    api_key: str,
    post: Callable[..., requests.Response] = requests.post,
) -> SyncResult:
    """Sends the manifest's event to the backend and sets `synced` to true on success.

    Safe to repeat: if the backend already has the event (it answers 409 because the clip
    file is stored once), the manifest is marked synced as well.
    """
    manifest = load_manifest(path)
    if manifest.get("synced"):
        return SyncResult(True, "already synced")

    try:
        response = post(
            f"{api_url}/events",
            json=event_payload(manifest, manifest_ref(path)),
            headers={"X-API-Key": api_key},
            timeout=10.0,
        )
    except requests.exceptions.RequestException as e:
        return SyncResult(False, f"backend unreachable ({type(e).__name__})")

    if response.status_code in (201, 409):
        manifest["synced"] = True
        save_manifest(path, manifest)
        stored = "saved" if response.status_code == 201 else "already in the database"
        return SyncResult(True, stored)
    return SyncResult(False, f"HTTP {response.status_code}: {response.text[:300]}")


def find_unsynced(manifests_dir: Path) -> Iterator[Path]:
    """Manifests whose event has not reached the backend yet, oldest first.

    Unreadable files are included too, so the caller reports them instead of skipping them.
    """
    for path in sorted(manifests_dir.glob("*.json")):
        try:
            synced = load_manifest(path).get("synced")
        except (OSError, ValueError):
            synced = False
        if not synced:
            yield path
