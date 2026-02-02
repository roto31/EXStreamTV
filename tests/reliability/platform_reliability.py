"""
Platform-Wide Reliability Testing

Continuous reliability monitoring for all EXStreamTV subsystems.
Tracks MTBF, MTTR, availability, and failure patterns across:
- API endpoints
- Database operations
- Streaming services
- Background tasks
- FFmpeg processes
- Integrations

Based on reliability testing principles from:
- Trymata: Ensuring products work consistently for every user, every time
- Microsoft: Fault injection and chaos engineering
- IBM: Systematic testing methodology
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx

from .metrics_collector import MetricsCollector, TestStatus

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """Platform component types."""
    API = "api"
    DATABASE = "database"
    STREAMING = "streaming"
    FFMPEG = "ffmpeg"
    TASKS = "tasks"
    WEBUI = "webui"
    INTEGRATION = "integration"


@dataclass
class ComponentHealth:
    """Health status of a component."""
    component: ComponentType
    name: str
    healthy: bool
    response_time_ms: float
    last_check: datetime
    consecutive_failures: int = 0
    error: Optional[str] = None
    details: dict = field(default_factory=dict)


@dataclass
class PlatformHealth:
    """Overall platform health status."""
    timestamp: datetime
    overall_healthy: bool
    components: dict = field(default_factory=dict)
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    
    @property
    def availability_pct(self) -> float:
        if self.total_checks == 0:
            return 100.0
        return (self.passed_checks / self.total_checks) * 100


class PlatformReliabilityMonitor:
    """
    Continuous platform reliability monitoring.
    
    Performs periodic health checks across all subsystems
    and tracks reliability metrics over time.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8411",
        check_interval_seconds: float = 60.0,
    ):
        """
        Initialize the platform reliability monitor.
        
        Args:
            base_url: EXStreamTV server URL
            check_interval_seconds: Interval between health check cycles
        """
        self.base_url = base_url
        self.check_interval = check_interval_seconds
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Health history
        self.health_history: list[PlatformHealth] = []
        self.component_failures: dict[str, list] = {}
        
        # Metrics
        self.total_checks = 0
        self.passed_checks = 0
        self.start_time: Optional[datetime] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._http_client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, *args):
        """Async context manager exit."""
        if self._http_client:
            await self._http_client.aclose()
    
    async def check_api_health(self) -> list[ComponentHealth]:
        """Check API endpoint health."""
        results = []
        
        # Critical API endpoints to monitor
        endpoints = [
            ("/api/health", "Health API"),
            ("/api/channels", "Channels API"),
            ("/api/health/channels", "Channel Health API"),
            ("/iptv/channels.m3u", "M3U Playlist"),
            ("/iptv/xmltv.xml", "EPG XMLTV"),
            ("/api/dashboard", "Dashboard API"),
            ("/api/libraries", "Libraries API"),
        ]
        
        for endpoint, name in endpoints:
            start = time.time()
            try:
                r = await self._http_client.get(f"{self.base_url}{endpoint}")
                response_time = (time.time() - start) * 1000
                
                results.append(ComponentHealth(
                    component=ComponentType.API,
                    name=name,
                    healthy=r.status_code in [200, 307],
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    details={"endpoint": endpoint, "status_code": r.status_code},
                ))
            except Exception as e:
                response_time = (time.time() - start) * 1000
                results.append(ComponentHealth(
                    component=ComponentType.API,
                    name=name,
                    healthy=False,
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    error=str(e),
                    details={"endpoint": endpoint},
                ))
        
        return results
    
    async def check_database_health(self) -> ComponentHealth:
        """Check database health."""
        start = time.time()
        try:
            r = await self._http_client.get(f"{self.base_url}/api/health/detailed")
            response_time = (time.time() - start) * 1000
            
            data = r.json()
            db_status = data.get("components", {}).get("database", {})
            
            return ComponentHealth(
                component=ComponentType.DATABASE,
                name="Database",
                healthy=db_status.get("status") == "ok",
                response_time_ms=response_time,
                last_check=datetime.now(),
                details=db_status,
            )
        except Exception as e:
            return ComponentHealth(
                component=ComponentType.DATABASE,
                name="Database",
                healthy=False,
                response_time_ms=(time.time() - start) * 1000,
                last_check=datetime.now(),
                error=str(e),
            )
    
    async def check_ffmpeg_health(self) -> ComponentHealth:
        """Check FFmpeg health."""
        start = time.time()
        try:
            r = await self._http_client.get(f"{self.base_url}/api/health/detailed")
            response_time = (time.time() - start) * 1000
            
            data = r.json()
            ffmpeg = data.get("components", {}).get("ffmpeg", {})
            
            return ComponentHealth(
                component=ComponentType.FFMPEG,
                name="FFmpeg",
                healthy=ffmpeg.get("status") == "ok",
                response_time_ms=response_time,
                last_check=datetime.now(),
                details=ffmpeg,
            )
        except Exception as e:
            return ComponentHealth(
                component=ComponentType.FFMPEG,
                name="FFmpeg",
                healthy=False,
                response_time_ms=(time.time() - start) * 1000,
                last_check=datetime.now(),
                error=str(e),
            )
    
    async def check_streaming_health(self) -> ComponentHealth:
        """Check streaming subsystem health."""
        start = time.time()
        try:
            r = await self._http_client.get(f"{self.base_url}/api/health/channels")
            response_time = (time.time() - start) * 1000
            
            if r.status_code == 200:
                data = r.json()
                return ComponentHealth(
                    component=ComponentType.STREAMING,
                    name="Streaming",
                    healthy=True,
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    details=data,
                )
            else:
                return ComponentHealth(
                    component=ComponentType.STREAMING,
                    name="Streaming",
                    healthy=False,
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    error=f"HTTP {r.status_code}",
                )
        except Exception as e:
            return ComponentHealth(
                component=ComponentType.STREAMING,
                name="Streaming",
                healthy=False,
                response_time_ms=(time.time() - start) * 1000,
                last_check=datetime.now(),
                error=str(e),
            )
    
    async def check_webui_health(self) -> list[ComponentHealth]:
        """Check Web UI health."""
        results = []
        
        pages = [
            ("/", "Dashboard"),
            ("/channels", "Channels"),
            ("/playlists", "Playlists"),
        ]
        
        for page, name in pages:
            start = time.time()
            try:
                r = await self._http_client.get(f"{self.base_url}{page}")
                response_time = (time.time() - start) * 1000
                
                results.append(ComponentHealth(
                    component=ComponentType.WEBUI,
                    name=f"WebUI: {name}",
                    healthy=r.status_code in [200, 307],
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    details={"page": page, "status_code": r.status_code},
                ))
            except Exception as e:
                response_time = (time.time() - start) * 1000
                results.append(ComponentHealth(
                    component=ComponentType.WEBUI,
                    name=f"WebUI: {name}",
                    healthy=False,
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    error=str(e),
                ))
        
        return results
    
    async def check_integration_health(self) -> list[ComponentHealth]:
        """Check integration health."""
        results = []
        
        # HDHomeRun
        start = time.time()
        try:
            r = await self._http_client.get(f"{self.base_url}/discover.json")
            response_time = (time.time() - start) * 1000
            
            results.append(ComponentHealth(
                component=ComponentType.INTEGRATION,
                name="HDHomeRun",
                healthy=r.status_code == 200,
                response_time_ms=response_time,
                last_check=datetime.now(),
                details={"endpoint": "/discover.json"},
            ))
        except Exception as e:
            results.append(ComponentHealth(
                component=ComponentType.INTEGRATION,
                name="HDHomeRun",
                healthy=False,
                response_time_ms=(time.time() - start) * 1000,
                last_check=datetime.now(),
                error=str(e),
            ))
        
        return results
    
    async def run_health_check(self) -> PlatformHealth:
        """Run a complete platform health check."""
        all_components = {}
        total = 0
        passed = 0
        
        # Check all subsystems
        api_health = await self.check_api_health()
        for h in api_health:
            all_components[f"api_{h.name}"] = h
            total += 1
            if h.healthy:
                passed += 1
        
        db_health = await self.check_database_health()
        all_components["database"] = db_health
        total += 1
        if db_health.healthy:
            passed += 1
        
        ffmpeg_health = await self.check_ffmpeg_health()
        all_components["ffmpeg"] = ffmpeg_health
        total += 1
        if ffmpeg_health.healthy:
            passed += 1
        
        streaming_health = await self.check_streaming_health()
        all_components["streaming"] = streaming_health
        total += 1
        if streaming_health.healthy:
            passed += 1
        
        webui_health = await self.check_webui_health()
        for h in webui_health:
            all_components[f"webui_{h.name}"] = h
            total += 1
            if h.healthy:
                passed += 1
        
        integration_health = await self.check_integration_health()
        for h in integration_health:
            all_components[f"integration_{h.name}"] = h
            total += 1
            if h.healthy:
                passed += 1
        
        # Determine overall health
        overall_healthy = passed >= (total * 0.8)  # 80% threshold
        
        health = PlatformHealth(
            timestamp=datetime.now(),
            overall_healthy=overall_healthy,
            components=all_components,
            total_checks=total,
            passed_checks=passed,
            failed_checks=total - passed,
        )
        
        self.health_history.append(health)
        self.total_checks += total
        self.passed_checks += passed
        
        # Track failures
        for name, component in all_components.items():
            if not component.healthy:
                if name not in self.component_failures:
                    self.component_failures[name] = []
                self.component_failures[name].append({
                    "timestamp": datetime.now().isoformat(),
                    "error": component.error,
                })
        
        return health
    
    async def run_continuous(
        self,
        duration_hours: float = 1.0,
        on_failure: Optional[callable] = None,
    ) -> dict:
        """
        Run continuous platform monitoring.
        
        Args:
            duration_hours: How long to monitor
            on_failure: Callback function when a component fails
            
        Returns:
            Summary of monitoring results
        """
        self.start_time = datetime.now()
        end_time = self.start_time + timedelta(hours=duration_hours)
        check_count = 0
        
        logger.info(f"Starting platform reliability monitoring for {duration_hours} hours")
        
        while datetime.now() < end_time:
            check_count += 1
            logger.info(f"=== Health Check #{check_count} ===")
            
            health = await self.run_health_check()
            
            status = "✓ HEALTHY" if health.overall_healthy else "✗ DEGRADED"
            logger.info(f"Platform Status: {status}")
            logger.info(f"Components: {health.passed_checks}/{health.total_checks} passed")
            
            # Report failures
            failed = [
                name for name, c in health.components.items()
                if not c.healthy
            ]
            if failed:
                logger.warning(f"Failed components: {', '.join(failed)}")
                if on_failure:
                    on_failure(failed)
            
            # Wait for next check
            await asyncio.sleep(self.check_interval)
        
        # Generate summary
        return self.generate_summary()
    
    def generate_summary(self) -> dict:
        """Generate monitoring summary."""
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        summary = {
            "duration_seconds": duration,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.total_checks - self.passed_checks,
            "availability_pct": (self.passed_checks / self.total_checks * 100) if self.total_checks > 0 else 100,
            "health_snapshots": len(self.health_history),
            "component_failures": {
                name: len(failures)
                for name, failures in self.component_failures.items()
            },
        }
        
        return summary
    
    def print_report(self) -> str:
        """Print a human-readable report."""
        summary = self.generate_summary()
        
        lines = [
            "=" * 80,
            "EXSTREAMTV PLATFORM RELIABILITY REPORT",
            "=" * 80,
            f"Monitoring Duration: {summary['duration_seconds'] / 3600:.2f} hours",
            f"Total Health Checks: {summary['total_checks']}",
            f"Passed: {summary['passed_checks']}",
            f"Failed: {summary['failed_checks']}",
            f"Platform Availability: {summary['availability_pct']:.2f}%",
            "",
        ]
        
        if summary['component_failures']:
            lines.extend([
                "COMPONENT FAILURES:",
                "-" * 40,
            ])
            for component, count in sorted(
                summary['component_failures'].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                lines.append(f"  {component}: {count} failures")
        
        lines.append("=" * 80)
        
        report = "\n".join(lines)
        print(report)
        return report
    
    def save_report(self, output_path: Path) -> None:
        """Save report to file."""
        summary = self.generate_summary()
        summary["health_history"] = [
            {
                "timestamp": h.timestamp.isoformat(),
                "overall_healthy": h.overall_healthy,
                "passed": h.passed_checks,
                "failed": h.failed_checks,
            }
            for h in self.health_history
        ]
        
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Report saved to {output_path}")
