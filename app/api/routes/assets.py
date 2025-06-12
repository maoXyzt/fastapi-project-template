from pathlib import Path
from typing import Annotated

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import AfterValidator

from app.core.config import settings

router = APIRouter(tags=["assets"])


def _is_valid_asset_path(path: Path) -> Path:
    path = settings.DEFAULT_ASSETS_FOLDER / path
    if not path.exists():
        raise ValueError(f'File not found: "{path}"')
    path_abs = path.absolute()
    if not path_abs.is_file():
        raise ValueError(f'Invalid path: "{path}"')
    if not path_abs.is_relative_to(settings.DEFAULT_ASSETS_FOLDER):
        # For security, prevent traversal outside current directory
        raise ValueError(f'Invalid path: "{path}"')
    return path_abs.relative_to(settings.DEFAULT_ASSETS_FOLDER)


AssetFilePath = Annotated[Path, AfterValidator(_is_valid_asset_path)]


@router.get("/assets/{path:path}", response_class=FileResponse)
async def get_default_asset(path: AssetFilePath):
    """Handle GET requests for files.

    Args:
        path (AssetFilePath): The path to the asset.

    Returns:
        FileResponse: The asset file response.
    """
    return settings.DEFAULT_ASSETS_FOLDER / path
