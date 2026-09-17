from pathlib import Path
import tomllib

PYPROJECT_TOML_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"

def get_version() -> str:
	"""Get the version of the application from pyproject.toml."""
	with open(PYPROJECT_TOML_PATH, "rb") as f:
		pyproject_data = tomllib.load(f)
	return pyproject_data["project"]["version"]
