"""
HDHomeRun Protocol Validator.

Validates:
- /discover.json — valid JSON, DeviceID 8 hex chars, correct schema
- /lineup.json — valid JSON, unique GuideNumbers
- /lineup_status.json — valid JSON
- /device.xml — valid XML, HDHomeRun schema
- Response latency < 500ms sustained
"""

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime

import logging

import httpx

logger = logging.getLogger(__name__)


@dataclass
class HDHomeRunValidationResult:
    """Result of HDHomeRun endpoint validation."""

    endpoint: str
    ok: bool
    latency_ms: float
    message: str | None


@dataclass
class HDHomeRunFullResult:
    """Full HDHomeRun protocol validation result."""

    discover: HDHomeRunValidationResult
    lineup: HDHomeRunValidationResult
    lineup_status: HDHomeRunValidationResult
    device: HDHomeRunValidationResult
    device_id: str | None
    guide_numbers: list[str]
    duplicate_guide_numbers: list[str]


def _valid_device_id(device_id: str) -> bool:
    """DeviceID must be 8 uppercase hex chars."""
    return bool(re.fullmatch(r"[0-9A-Fa-f]{8}", str(device_id).strip()))


async def validate_discover(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
    max_latency_ms: float = 500.0,
) -> tuple[HDHomeRunValidationResult, str | None]:
    """Validate /hdhomerun/discover.json."""
    url = f"{base_url.rstrip('/')}/hdhomerun/discover.json"
    start = datetime.utcnow()
    try:
        c = client or httpx.AsyncClient(timeout=10.0)
        resp = await c.get(url)
        latency = (datetime.utcnow() - start).total_seconds() * 1000

        if resp.status_code != 200:
            return (
                HDHomeRunValidationResult(
                    endpoint="discover.json",
                    ok=False,
                    latency_ms=latency,
                    message=f"HTTP {resp.status_code}",
                ),
                None,
            )

        data = resp.json()
        device_id = data.get("DeviceID", "")
        if not _valid_device_id(device_id):
            return (
                HDHomeRunValidationResult(
                    endpoint="discover.json",
                    ok=False,
                    latency_ms=latency,
                    message=f"Invalid DeviceID: {device_id}",
                ),
                None,
            )

        required = ("BaseURL", "LineupURL", "FriendlyName", "TunerCount")
        for key in required:
            if key not in data:
                return (
                    HDHomeRunValidationResult(
                        endpoint="discover.json",
                        ok=False,
                        latency_ms=latency,
                        message=f"Missing {key}",
                    ),
                    None,
                )

        ok = latency <= max_latency_ms
        return (
            HDHomeRunValidationResult(
                endpoint="discover.json",
                ok=ok,
                latency_ms=latency,
                message=None if ok else f"Latency {latency:.0f}ms > {max_latency_ms}ms",
            ),
            device_id,
        )
    except Exception as e:
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return (
            HDHomeRunValidationResult(
                endpoint="discover.json",
                ok=False,
                latency_ms=latency,
                message=str(e),
            ),
            None,
        )


async def validate_lineup(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
    max_latency_ms: float = 500.0,
) -> tuple[HDHomeRunValidationResult, list[str], list[str]]:
    """Validate /hdhomerun/lineup.json and check GuideNumber uniqueness."""
    url = f"{base_url.rstrip('/')}/hdhomerun/lineup.json"
    start = datetime.utcnow()
    guide_numbers: list[str] = []
    duplicates: list[str] = []
    try:
        c = client or httpx.AsyncClient(timeout=10.0)
        resp = await c.get(url)
        latency = (datetime.utcnow() - start).total_seconds() * 1000

        if resp.status_code != 200:
            return (
                HDHomeRunValidationResult(
                    endpoint="lineup.json",
                    ok=False,
                    latency_ms=latency,
                    message=f"HTTP {resp.status_code}",
                ),
                [],
                [],
            )

        data = resp.json()
        if not isinstance(data, list):
            return (
                HDHomeRunValidationResult(
                    endpoint="lineup.json",
                    ok=False,
                    latency_ms=latency,
                    message="Expected array",
                ),
                [],
                [],
            )

        seen: set[str] = set()
        for entry in data:
            gn = str(entry.get("GuideNumber", ""))
            if gn:
                guide_numbers.append(gn)
                if gn in seen:
                    duplicates.append(gn)
                seen.add(gn)

        ok = latency <= max_latency_ms and len(duplicates) == 0
        return (
            HDHomeRunValidationResult(
                endpoint="lineup.json",
                ok=ok,
                latency_ms=latency,
                message=None
                if ok
                else (f"Duplicates: {duplicates}" if duplicates else f"Latency {latency:.0f}ms"),
            ),
            guide_numbers,
            duplicates,
        )
    except Exception as e:
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return (
            HDHomeRunValidationResult(
                endpoint="lineup.json",
                ok=False,
                latency_ms=latency,
                message=str(e),
            ),
            [],
            [],
        )


async def validate_lineup_status(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> HDHomeRunValidationResult:
    """Validate /hdhomerun/lineup_status.json."""
    url = f"{base_url.rstrip('/')}/hdhomerun/lineup_status.json"
    start = datetime.utcnow()
    try:
        c = client or httpx.AsyncClient(timeout=10.0)
        resp = await c.get(url)
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        if resp.status_code != 200:
            return HDHomeRunValidationResult(
                endpoint="lineup_status.json",
                ok=False,
                latency_ms=latency,
                message=f"HTTP {resp.status_code}",
            )
        resp.json()
        return HDHomeRunValidationResult(
            endpoint="lineup_status.json",
            ok=True,
            latency_ms=latency,
            message=None,
        )
    except Exception as e:
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return HDHomeRunValidationResult(
            endpoint="lineup_status.json",
            ok=False,
            latency_ms=latency,
            message=str(e),
        )


async def validate_device_xml(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> HDHomeRunValidationResult:
    """Validate /hdhomerun/device.xml — valid XML, HDHomeRun/UPnP schema."""
    url = f"{base_url.rstrip('/')}/hdhomerun/device.xml"
    start = datetime.utcnow()
    try:
        c = client or httpx.AsyncClient(timeout=10.0)
        resp = await c.get(url)
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        if resp.status_code != 200:
            return HDHomeRunValidationResult(
                endpoint="device.xml",
                ok=False,
                latency_ms=latency,
                message=f"HTTP {resp.status_code}",
            )
        root = ET.fromstring(resp.text)
        if root.tag != "root" or "device" not in [c.tag for c in root]:
            return HDHomeRunValidationResult(
                endpoint="device.xml",
                ok=False,
                latency_ms=latency,
                message="Invalid HDHomeRun device schema",
            )
        return HDHomeRunValidationResult(
            endpoint="device.xml",
            ok=True,
            latency_ms=latency,
            message=None,
        )
    except ET.ParseError as e:
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return HDHomeRunValidationResult(
            endpoint="device.xml",
            ok=False,
            latency_ms=latency,
            message=f"XML parse error: {e}",
        )
    except Exception as e:
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        return HDHomeRunValidationResult(
            endpoint="device.xml",
            ok=False,
            latency_ms=latency,
            message=str(e),
        )


async def validate_hdhomerun_protocol(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> HDHomeRunFullResult:
    """Run full HDHomeRun protocol validation."""
    discover_res, device_id = await validate_discover(base_url, client=client)
    lineup_res, guide_numbers, duplicate_guide_numbers = await validate_lineup(
        base_url, client=client
    )
    lineup_status_res = await validate_lineup_status(base_url, client=client)
    device_res = await validate_device_xml(base_url, client=client)

    return HDHomeRunFullResult(
        discover=discover_res,
        lineup=lineup_res,
        lineup_status=lineup_status_res,
        device=device_res,
        device_id=device_id,
        guide_numbers=guide_numbers,
        duplicate_guide_numbers=duplicate_guide_numbers,
    )
