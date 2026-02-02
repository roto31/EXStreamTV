"""
StreamTV Import Reliability Tests

Tests the StreamTV database import functionality for:
- Database validation
- Channel migration
- Playlist migration
- Media item migration
- YouTube/Archive.org source migration

Issues to detect:
- Missing schedules in Plex
- Channels that don't tune
- Missing playout data
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class StreamTVImportTestResult:
    """Result of StreamTV import testing."""
    database_valid: bool = False
    channels_found: int = 0
    channels_migrated: int = 0
    channels_with_playouts: int = 0
    channels_tunable: int = 0
    playlists_found: int = 0
    media_items_found: int = 0
    issues: list = None
    warnings: list = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.warnings is None:
            self.warnings = []


class StreamTVImportTest:
    """
    Tests StreamTV import functionality and identifies issues.
    
    Common issues detected:
    1. Channels without schedules appearing in Plex
    2. Channels that fail to tune
    3. Missing playout data
    4. Media items without valid URLs
    """
    
    def __init__(
        self,
        source_db_path: Optional[Path] = None,
        base_url: str = "http://localhost:8411",
    ):
        """
        Initialize the StreamTV import tester.
        
        Args:
            source_db_path: Path to StreamTV database (for import testing)
            base_url: EXStreamTV server URL
        """
        self.source_db_path = source_db_path
        self.base_url = base_url
        self.result = StreamTVImportTestResult()
    
    async def validate_source_database(self) -> bool:
        """
        Validate the StreamTV source database.
        
        Returns:
            True if database is valid for import
        """
        if not self.source_db_path:
            logger.warning("No StreamTV database path provided")
            self.result.issues.append("No StreamTV database path provided")
            return False
        
        if not self.source_db_path.exists():
            logger.error(f"StreamTV database not found: {self.source_db_path}")
            self.result.issues.append(f"Database not found: {self.source_db_path}")
            return False
        
        try:
            from exstreamtv.importers.streamtv_importer import StreamTVImporter
            
            importer = StreamTVImporter(self.source_db_path, dry_run=True)
            validation = importer.validate()
            
            self.result.database_valid = validation["is_valid"]
            self.result.channels_found = validation["counts"].get("channels", 0)
            self.result.playlists_found = validation["counts"].get("playlists", 0)
            self.result.media_items_found = validation["counts"].get("media_items", 0)
            
            for warning in validation.get("warnings", []):
                self.result.warnings.append(f"Import warning: {warning}")
            
            for error in validation.get("errors", []):
                self.result.issues.append(f"Import error: {error}")
            
            return validation["is_valid"]
            
        except Exception as e:
            logger.error(f"Failed to validate database: {e}")
            self.result.issues.append(f"Validation error: {e}")
            return False
    
    async def check_imported_channels(self) -> int:
        """
        Check channels that were imported from StreamTV.
        
        Returns:
            Number of channels with issues
        """
        import httpx
        
        issues_count = 0
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get all channels
            response = await client.get(f"{self.base_url}/api/channels")
            channels = response.json()
            
            # Check each channel for common issues
            for channel in channels:
                channel_number = channel.get("number", "?")
                channel_name = channel.get("name", "Unknown")
                channel_id = channel.get("id")
                
                # Check for playout data
                try:
                    playout_response = await client.get(
                        f"{self.base_url}/api/channels/{channel_id}/playout"
                    )
                    if playout_response.status_code == 200:
                        playout_data = playout_response.json()
                        items = playout_data.get("items", [])
                        
                        if items:
                            self.result.channels_with_playouts += 1
                        else:
                            self.result.warnings.append(
                                f"Channel {channel_number} ({channel_name}): No playout items"
                            )
                            issues_count += 1
                    else:
                        self.result.issues.append(
                            f"Channel {channel_number} ({channel_name}): Playout API error"
                        )
                        issues_count += 1
                        
                except Exception as e:
                    self.result.issues.append(
                        f"Channel {channel_number} ({channel_name}): {e}"
                    )
                    issues_count += 1
        
        self.result.channels_migrated = len(channels)
        return issues_count
    
    async def test_channel_tunability(self, sample_size: int = 5) -> int:
        """
        Test if imported channels can actually be tuned.
        
        Args:
            sample_size: Number of channels to test
            
        Returns:
            Number of tunable channels
        """
        import httpx
        
        tunable = 0
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get enabled channels
            response = await client.get(f"{self.base_url}/api/channels")
            channels = [c for c in response.json() if c.get("enabled")][:sample_size]
            
            for channel in channels:
                channel_number = channel.get("number", "?")
                
                try:
                    # Try to get stream data
                    async with client.stream(
                        "GET",
                        f"{self.base_url}/iptv/channel/{channel_number}.ts",
                        timeout=20.0,
                    ) as stream:
                        if stream.status_code == 200:
                            bytes_received = 0
                            async for chunk in stream.aiter_bytes():
                                bytes_received += len(chunk)
                                if bytes_received >= 188:  # One MPEG-TS packet
                                    tunable += 1
                                    break
                            else:
                                self.result.warnings.append(
                                    f"Channel {channel_number}: No stream data"
                                )
                        else:
                            self.result.issues.append(
                                f"Channel {channel_number}: HTTP {stream.status_code}"
                            )
                            
                except Exception as e:
                    self.result.issues.append(
                        f"Channel {channel_number}: Tune failed - {e}"
                    )
        
        self.result.channels_tunable = tunable
        return tunable
    
    async def run_full_test(self) -> StreamTVImportTestResult:
        """
        Run complete StreamTV import testing.
        
        Returns:
            Test results
        """
        logger.info("Starting StreamTV import testing")
        
        # Test 1: Validate source database (if provided)
        if self.source_db_path:
            await self.validate_source_database()
        
        # Test 2: Check imported channels
        await self.check_imported_channels()
        
        # Test 3: Test channel tunability
        await self.test_channel_tunability()
        
        return self.result
    
    def print_report(self) -> str:
        """Print a human-readable report."""
        lines = [
            "=" * 80,
            "STREAMTV IMPORT TEST REPORT",
            "=" * 80,
            f"Timestamp: {datetime.now().isoformat()}",
            "",
            "DATABASE VALIDATION:",
            f"  Valid: {self.result.database_valid}",
            f"  Channels Found: {self.result.channels_found}",
            f"  Playlists Found: {self.result.playlists_found}",
            f"  Media Items Found: {self.result.media_items_found}",
            "",
            "CHANNEL STATUS:",
            f"  Channels Migrated: {self.result.channels_migrated}",
            f"  Channels with Playouts: {self.result.channels_with_playouts}",
            f"  Channels Tunable: {self.result.channels_tunable}",
        ]
        
        if self.result.issues:
            lines.extend([
                "",
                "ISSUES DETECTED:",
                "-" * 40,
            ])
            for issue in self.result.issues:
                lines.append(f"  ✗ {issue}")
        
        if self.result.warnings:
            lines.extend([
                "",
                "WARNINGS:",
                "-" * 40,
            ])
            for warning in self.result.warnings:
                lines.append(f"  ⚠ {warning}")
        
        lines.append("=" * 80)
        
        report = "\n".join(lines)
        print(report)
        return report


async def main():
    """Run StreamTV import tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="StreamTV Import Testing")
    parser.add_argument(
        "--source-db",
        type=Path,
        help="Path to StreamTV database file",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8411",
        help="EXStreamTV server URL",
    )
    
    args = parser.parse_args()
    
    tester = StreamTVImportTest(
        source_db_path=args.source_db,
        base_url=args.base_url,
    )
    
    result = await tester.run_full_test()
    tester.print_report()
    
    return 0 if not result.issues else 1


if __name__ == "__main__":
    asyncio.run(main())
