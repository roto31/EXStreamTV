"""
EXStreamTV Reliability and Regression Testing Framework

This module provides comprehensive reliability and regression testing capabilities
following industry best practices from:
- IBM Regression Testing Guidelines
- LeapWork Regression Testing Framework
- Microsoft Power Platform Reliability Testing Strategy
- GeeksforGeeks Software Testing Standards
- Trymata Reliability Testing Methodology

Key Metrics Tracked:
- MTBF (Mean Time Between Failures)
- MTTR (Mean Time To Repair)
- Failure Rate
- Task Success Rate
- Availability Percentage

Platform Coverage:
- Core System (health, database, FFmpeg)
- API Endpoints (45+ modules)
- Streaming Components
- Media Libraries
- AI/Agent Components
- Task Scheduler
- FFmpeg Pipeline
- Integrations (HDHomeRun, IPTV, Notifications)
- Web UI
"""

from .channel_reliability import ChannelReliabilityTest
from .regression_suite import RegressionTestSuite
from .metrics_collector import MetricsCollector
from .overnight_test import OvernightChannelTest
from .platform_regression_suite import PlatformRegressionSuite, Subsystem, Priority
from .platform_reliability import PlatformReliabilityMonitor
from .streamtv_import_test import StreamTVImportTest

__all__ = [
    # Channel-specific testing
    "ChannelReliabilityTest",
    "OvernightChannelTest",
    
    # Regression testing
    "RegressionTestSuite",
    "PlatformRegressionSuite",
    
    # Reliability monitoring
    "PlatformReliabilityMonitor",
    
    # Import testing
    "StreamTVImportTest",
    
    # Metrics
    "MetricsCollector",
    
    # Enums
    "Subsystem",
    "Priority",
]
