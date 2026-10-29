from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.auth import router as auth_router
from app.api.cameras import router as cameras_router
from app.api.events import router as events_router
from app.api.settings import router as settings_router
from app.api.users import router as users_router
from app.api.videos import router as videos_router
from app.core.config import get_settings
from app.core.version import get_version
from app.db.models import Camera
from app.db.session import SessionFactory

settings = get_settings()

DEV_CAMERA_NAME = "test_camera_01"


def seed_dev_camera() -> None:
    """Gives the worker's default camera name something to resolve to in development."""
    with SessionFactory() as session:
        if session.scalar(select(Camera).where(Camera.name == DEV_CAMERA_NAME)) is None:
            # `cameras.stream_url` is NOT NULL, UNIQUE and must be an `rtsp://` URL.
            session.add(
                Camera(name=DEV_CAMERA_NAME, stream_url=f"rtsp://127.0.0.1:8554/{DEV_CAMERA_NAME}")
            )
            session.commit()
            print(f"Seeded development camera {DEV_CAMERA_NAME!r}.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    if settings.environment == "development":
        seed_dev_camera()
    yield


app = FastAPI(
    title=settings.app_name,
    version=get_version(),
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(events_router, prefix=settings.api_prefix)
app.include_router(videos_router, prefix=settings.api_prefix)
app.include_router(cameras_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
app.include_router(settings_router, prefix=settings.api_prefix)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
    }
