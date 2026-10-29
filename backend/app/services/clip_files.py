"""Deleting clips: the video and manifest files, and the `deleting` -> `deleted` states."""

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.storage import recording_path
from app.db.enums import VideoStatus
from app.db.models import VideoClip


def clip_files(clip: VideoClip) -> list[tuple[str, ...]]:
    """The clip's files as path parts inside recordings/: the video, then its manifest."""
    files = []
    if clip.filepath:
        files.append((clip.filepath,))
    # Clips posted without a manifest have a `placeholder/<uuid>` reference: no file.
    if clip.source_manifest_ref.startswith("manifests/"):
        files.append(tuple(clip.source_manifest_ref.split("/")))
    return files


def remove_clip_files(clip: VideoClip) -> None:
    """Removes the clip's files. A file that is already gone counts as removed.

    Raises `OSError` when a file exists but can't be removed (on Windows, for example,
    while someone is streaming it).
    """
    for parts in clip_files(clip):
        try:
            path = recording_path(*parts)
        except ValueError:
            # Not a plain name inside recordings/: never delete anything outside it.
            continue
        path.unlink(missing_ok=True)


def delete_clips(session: Session, clips: Iterable[VideoClip]) -> int:
    """Deletes the clips' files in two committed steps; returns how many could not be removed.

    1. Mark every clip `deleting` and commit, so a crash halfway leaves a visible state
       instead of a `ready` clip whose file is gone.
    2. Remove the files; each clip whose files are gone becomes `deleted`. A clip whose
       file could not be removed stays `deleting`, and deleting again retries it.
    """
    to_delete = [clip for clip in clips if clip.status != VideoStatus.DELETED]
    if not to_delete:
        return 0

    now = datetime.now(UTC)
    for clip in to_delete:
        if clip.status != VideoStatus.DELETING:
            clip.status = VideoStatus.DELETING
            clip.delete_requested_at = now
            clip.updated_at = now
    session.commit()

    failed = 0
    for clip in to_delete:
        try:
            remove_clip_files(clip)
        except OSError:
            failed += 1
            continue
        now = datetime.now(UTC)
        clip.status = VideoStatus.DELETED
        clip.deleted_at = now
        clip.updated_at = now
    session.commit()
    return failed
