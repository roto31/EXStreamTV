"""API endpoints for importing channels from YAML"""

import logging
import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

try:
    import magic
except ImportError:
    magic = None  # Optional dependency; handled gracefully
import os

logger = logging.getLogger(__name__)

from typing import Any

from ..api.schemas import ChannelResponse
from ..config import get_config
from ..database import get_db

# Get config at module level
config = get_config()
from ..importers import (
    M3UEntry,
    M3UImporter,
    M3UMetadataEnricher,
    M3UParser,
    import_channels_from_yaml,
)
from ..validation import ValidationError, YAMLValidator

router = APIRouter(prefix="/import", tags=["Import"])

from ..constants import MEGABYTE

# Maximum file size: 5 MB
MAX_FILE_SIZE = 5 * MEGABYTE

# Allowed MIME types for YAML files
ALLOWED_MIME_TYPES = {
    "text/yaml",
    "text/x-yaml",
    "application/x-yaml",
    "application/yaml",
    "text/plain",  # Some systems report YAML as text/plain
}

# Allowed file extensions
ALLOWED_EXTENSIONS = {".yaml", ".yml"}


def validate_file_upload(file: UploadFile) -> None:
    """Validate uploaded file for security."""
    # Check filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Check for path traversal attempts
    if ".." in file.filename or "/" in file.filename or "\\" in file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename: path traversal detected")

    # Check content type if provided
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"Unexpected content type: {file.content_type} for file {file.filename}")


def validate_file_content(file_path: Path) -> None:
    """Validate file content for security.

    Args:
        file_path: Path to file to validate

    Raises:
        HTTPException: If file content validation fails
    """
    # Check file size
    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, detail=f"File too large: {file_size} bytes (max {MAX_FILE_SIZE} bytes)"
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Try to detect MIME type using python-magic if available
    try:
        import magic

        mime_type = magic.from_file(str(file_path), mime=True)
        if mime_type not in ALLOWED_MIME_TYPES:
            logger.warning(f"File MIME type mismatch: {mime_type} for {file_path}")
    except ImportError:
        # python-magic not available, skip MIME type check
        pass
    except Exception as e:
        logger.debug(f"Could not detect MIME type: {e}")

    # Validate YAML syntax and safety
    try:
        content = file_path.read_text(encoding="utf-8")
        # Check for potentially dangerous YAML tags
        if "!!python" in content or "!!python/object" in content:
            raise HTTPException(
                status_code=400, detail="YAML file contains unsafe Python object tags"
            )

        # Parse with safe loader
        yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML syntax: {e}")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400, detail="File encoding error: file must be UTF-8 encoded"
        )


@router.post("/channels/yaml", response_model=list[ChannelResponse])
async def import_channels_yaml(
    yaml_file: UploadFile = File(...),
    validate: bool = Query(True, description="Validate YAML against JSON schema"),
    db: Session = Depends(get_db),
) -> list[ChannelResponse]:
    """Import channels from uploaded YAML file.

    Creates channels, collections, playlists, and media items from YAML configuration.
    Optionally validates the YAML file against JSON schema before import.

    Args:
        yaml_file: Uploaded YAML file
        validate: Whether to validate YAML against JSON schema
        db: Database session

    Returns:
        list[ChannelResponse]: List of imported channels

    Raises:
        HTTPException: If file validation or import fails

    Security: File is validated for type, size, and content before processing.
    """
    # Validate file upload
    validate_file_upload(yaml_file)

    # Save uploaded file temporarily
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as tmp_file:
            from ..constants import DEFAULT_BUFFER_SIZE

            # Read file in chunks to prevent memory issues
            chunk_size = DEFAULT_BUFFER_SIZE
            total_size = 0
            while True:
                chunk = await yaml_file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    tmp_file.close()
                    os.unlink(tmp_file.name)
                    raise HTTPException(
                        status_code=400, detail=f"File too large (max {MAX_FILE_SIZE} bytes)"
                    )
                tmp_file.write(chunk)
        tmp_path = Path(tmp_file.name)

        # Validate file content
        validate_file_content(tmp_path)

        # Validate if requested
        if validate:
            try:
                validator = YAMLValidator()
                result = validator.validate_channel_file(tmp_path)
                if not result.get("valid", False):
                    errors = result.get("errors", [])
                    error_detail = (
                        f"Validation failed: {', '.join(errors[:5])}"  # Show first 5 errors
                    )
                    if len(errors) > 5:
                        error_detail += f" (and {len(errors) - 5} more errors)"
                    raise HTTPException(status_code=400, detail=error_detail)
            except ValidationError as e:
                # Include detailed errors in the response
                error_detail = e.message
                if hasattr(e, "errors") and e.errors:
                    error_detail += "\n\nDetailed errors:\n" + "\n".join(
                        f"  - {err}" for err in e.errors[:10]
                    )  # Limit to first 10 errors
                raise HTTPException(status_code=400, detail=error_detail)

        # Import channels
        channels = await import_channels_from_yaml(tmp_path, validate=validate)

        logger.info(f"Successfully imported {len(channels)} channels from {yaml_file.filename}")
        return channels
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing channels from {yaml_file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error importing channels: {e!s}")
    finally:
        # Clean up temporary file securely
        if tmp_path and tmp_path.exists():
            try:
                # Overwrite file before deletion (security best practice)
                with open(tmp_path, "wb") as f:
                    f.write(b"\x00" * min(tmp_path.stat().st_size, 1024))  # Overwrite first KB
                tmp_path.unlink()
            except Exception as e:
                logger.warning(f"Could not securely delete temporary file {tmp_path}: {e}")


@router.post("/channels/yaml/path", response_model=list[ChannelResponse])
async def import_channels_yaml_path(
    file_path: str,
    validate: bool = Query(True, description="Validate YAML against JSON schema"),
    db: Session = Depends(get_db),
) -> list[ChannelResponse]:
    """Import channels from YAML file path.

    Creates channels, collections, playlists, and media items from YAML configuration.
    Optionally validates the YAML file against JSON schema before import.

    Args:
        file_path: Path to YAML file
        validate: Whether to validate YAML against JSON schema
        db: Database session

    Returns:
        list[ChannelResponse]: List of imported channels

    Raises:
        HTTPException: If file validation or import fails
    """
    yaml_path = Path(file_path)

    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"YAML file not found: {file_path}")

    if yaml_path.suffix not in (".yaml", ".yml"):
        raise HTTPException(status_code=400, detail="File must be a YAML file (.yaml or .yml)")

    from ..constants import MEGABYTE

    # Enforce size limit (5 MB) for path-based imports
    if yaml_path.stat().st_size > 5 * MEGABYTE:
        raise HTTPException(status_code=400, detail="YAML file too large (max 5 MB)")

    # Basic YAML safety check to reject non-safe tags
    try:
        yaml.safe_load(yaml_path.read_text())
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    try:
        # Validate if requested
        if validate:
            try:
                validator = YAMLValidator()
                result = validator.validate_channel_file(yaml_path)
                if not result.get("valid", False):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Validation failed: {', '.join(result.get('errors', []))}",
                    )
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=f"Validation error: {e.message}")

        # Import channels
        channels = await import_channels_from_yaml(yaml_path, validate=validate)

        return channels
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error importing channels: {e!s}")


@router.post("/m3u/preview")
async def preview_m3u_channels(
    request: Request,
    m3u_url: str = Query(..., description="URL to M3U file"),
    enrich_metadata: bool = Query(True, description="Enrich with iptv-org metadata"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Parse M3U file and return channel preview list with metadata.

    Does not create any database records - only parses and returns preview data.

    Args:
        request: FastAPI request object
        m3u_url: URL or file path to M3U file
        enrich_metadata: Whether to enrich with iptv-org metadata
        db: Database session

    Returns:
        list[dict[str, Any]]: List of channel preview dictionaries

    Raises:
        HTTPException: If M3U parsing fails
    """
    # Check if M3U module is enabled
    if not config.m3u.enabled:
        raise HTTPException(
            status_code=403,
            detail="M3U module is not enabled. Please enable it in the M3U import page.",
        )

    try:
        # Validate URL
        from urllib.parse import urlparse

        parsed = urlparse(m3u_url)
        if parsed.scheme not in ("http", "https") and not Path(m3u_url).exists():
            raise HTTPException(status_code=400, detail="Invalid M3U URL or file path")

        # Parse M3U file
        # M3UImporter, M3UParser, and M3UMetadataEnricher are already imported at the top

        importer = M3UImporter(db)
        try:
            preview_list = await importer.parse_and_preview(m3u_url)

            # Enrich with metadata if requested
            if enrich_metadata:
                enricher = M3UMetadataEnricher()
                try:
                    # We need to re-parse to get M3UEntry objects for enrichment
                    entries = await M3UParser.parse_file(m3u_url)
                    enriched_entries = await enricher.enrich_entries(entries)

                    # Merge enriched data into preview list
                    for i, entry in enumerate(enriched_entries):
                        if i < len(preview_list):
                            preview = preview_list[i]
                            if entry.extra_attrs.get("country"):
                                preview["country"] = entry.extra_attrs["country"]
                            if entry.extra_attrs.get("categories"):
                                preview["categories"] = entry.extra_attrs["categories"].split(",")
                            if entry.extra_attrs.get("network"):
                                preview["network"] = entry.extra_attrs["network"]
                            if entry.extra_attrs.get("language"):
                                preview["language"] = entry.extra_attrs["language"]
                finally:
                    await enricher.close()

            return preview_list
        finally:
            importer.close()

    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error previewing M3U channels: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error parsing M3U file: {e!s}")


class M3UImportRequest(BaseModel):
    m3u_url: str
    selected_channels: list[int]
    channel_number_start: int = 1000
    auto_assign_numbers: bool = True
    create_playlists: bool = True


@router.post("/m3u/import", response_model=list[ChannelResponse])
async def import_m3u_channels(
    request: Request, import_request: M3UImportRequest, db: Session = Depends(get_db)
) -> list[ChannelResponse]:
    """Import selected channels from M3U file.

    Creates channels, media items, and playlists for the selected channels.

    Args:
        request: FastAPI request object
        import_request: M3U import request with selected channels
        db: Database session

    Returns:
        list[ChannelResponse]: List of imported channels

    Raises:
        HTTPException: If import fails
    """
    # Check if M3U module is enabled
    if not config.m3u.enabled:
        raise HTTPException(
            status_code=403,
            detail="M3U module is not enabled. Please enable it in the M3U import page.",
        )

    if not import_request.selected_channels:
        raise HTTPException(status_code=400, detail="No channels selected for import")

    try:
        # Validate URL
        from urllib.parse import urlparse

        parsed = urlparse(import_request.m3u_url)
        if parsed.scheme not in ("http", "https") and not Path(import_request.m3u_url).exists():
            raise HTTPException(status_code=400, detail="Invalid M3U URL or file path")

        # Import selected channels
        # M3UImporter is already imported at the top
        importer = M3UImporter(db)
        try:
            channels = await importer.import_selected(
                import_request.m3u_url,
                import_request.selected_channels,
                channel_number_start=import_request.channel_number_start,
                auto_assign_numbers=import_request.auto_assign_numbers,
                create_playlists=import_request.create_playlists,
            )

            logger.info(f"Successfully imported {len(channels)} channels from M3U")

            # Convert to response models for proper serialization
            from ..api.schemas import ChannelResponse

            response_channels = [ChannelResponse.model_validate(ch) for ch in channels]
            return response_channels
        finally:
            importer.close()

    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing M3U channels: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error importing channels: {e!s}")


@router.get("/m3u/metadata/{tvg_id}")
async def get_m3u_channel_metadata(
    tvg_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Get metadata for a specific channel by tvg-id from iptv-org API.

    Optional endpoint for metadata enrichment.

    Args:
        tvg_id: TV guide ID for the channel
        db: Database session

    Returns:
        dict[str, Any]: Channel metadata dictionary

    Raises:
        HTTPException: If metadata retrieval fails
    """
    # Check if M3U module is enabled
    if not config.m3u.enabled:
        raise HTTPException(status_code=403, detail="M3U module is not enabled")

    try:
        # M3UMetadataEnricher and M3UEntry are already imported at the top

        enricher = M3UMetadataEnricher()
        try:
            # Create a dummy entry to enrich
            entry = M3UEntry(tvg_id=tvg_id)
            enriched = await enricher.enrich_entry(entry)

            return {"tvg_id": tvg_id, "metadata": enriched.extra_attrs}
        finally:
            await enricher.close()
    except Exception as e:
        logger.error(f"Error fetching metadata for {tvg_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching metadata: {e!s}")
