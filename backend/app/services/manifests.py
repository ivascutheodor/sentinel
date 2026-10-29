"""Checks a clip against the manifest the worker sealed next to it."""

import hashlib
from pathlib import Path

from pydantic import ValidationError

from app.core.storage import RECORDINGS_DIR
from app.schemas.manifests import ClipManifest


class ManifestError(Exception):
    """The manifest is missing, unreadable, or does not describe the posted clip."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(ref: str, camera_name: str, video_file: str, size_bytes: int) -> str:
    """Returns the video's SHA-256 if the manifest and the file on disk both match the event.

    The worker's word is not enough: the file is hashed again here, so a clip that was
    changed or replaced after recording is refused instead of being stored as evidence.
    """
    manifest_path = RECORDINGS_DIR / ref  # `ref` is already restricted to manifests/<name>.json
    if not manifest_path.is_file():
        raise ManifestError(f"Manifest {ref!r} not found.")
    try:
        manifest = ClipManifest.model_validate_json(manifest_path.read_bytes())
    except ValidationError as exc:
        raise ManifestError(
            f"Manifest {ref!r} is not valid ({exc.error_count()} error(s))."
        ) from exc

    if manifest.camera_id != camera_name:
        raise ManifestError(f"Manifest {ref!r} belongs to camera {manifest.camera_id!r}.")
    if manifest.video.file != video_file:
        raise ManifestError(f"Manifest {ref!r} describes {manifest.video.file!r}, not this clip.")

    if Path(video_file).name != video_file:
        raise ManifestError("video_path must be a plain file name.")
    video_path = RECORDINGS_DIR / video_file
    if not video_path.is_file():
        raise ManifestError(f"Clip {video_file!r} not found on disk.")

    actual_size = video_path.stat().st_size
    if actual_size != manifest.video.size_bytes or actual_size != size_bytes:
        raise ManifestError(f"Clip {video_file!r} size does not match its manifest.")
    digest = sha256_of(video_path)
    if digest != manifest.video.sha256:
        raise ManifestError(f"Clip {video_file!r} does not match its manifest (SHA-256 differs).")
    return digest
