from fastapi import FastAPI

from app.api.events import router as events_router
from app.api.videos import router as videos_router
from app.core.config import get_settings
from app.core.version import get_version

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=get_version(),
    debug=settings.debug,
)
app.include_router(events_router, prefix=settings.api_prefix)
app.include_router(videos_router, prefix=settings.api_prefix)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
    }
