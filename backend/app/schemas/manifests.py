from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

# What `video_clips.source_manifest_ref` may hold: one plain file name inside manifests/,
# never a path the client could point elsewhere.
ManifestRef = Annotated[str, StringConstraints(pattern=r"^manifests/[A-Za-z0-9._-]+\.json$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ManifestVideo(BaseModel):
    file: str
    size_bytes: int = Field(gt=0)
    sha256: Sha256


class ClipManifest(BaseModel):
    """The parts of a worker manifest the backend checks. Other fields (times, fps,
    `synced`, ...) are allowed and ignored here."""

    schema_version: Literal[1]
    camera_id: str
    video: ManifestVideo
