from fastapi import FastAPI
from importlib.metadata import version
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
	title=settings.APP_NAME,
	version=version("sentinel-backend"),
	debug=settings.DEBUG,
)