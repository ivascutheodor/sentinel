from fastapi import FastAPI

from app.core.config import get_settings
from app.core.version import get_version

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=get_version(),
    debug=settings.debug,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
    }
