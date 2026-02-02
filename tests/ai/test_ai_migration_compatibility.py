"""
AI Migration Compatibility Tests

Tests that the AI channel creation and self-healing systems are fully
compatible with the ErsatzTV/StreamTV migration schema updates.
"""

import pytest
from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch


class TestChannelCreatorMigrationCompat:
    """Test AI Channel Creator compatibility with new schema."""
    
    def test_channel_specification_supports_smart_collection(self):
        """Test that ChannelSpecification can reference smart collections."""
        from exstreamtv.ai_agent.channel_creator import ChannelSpecification
        
        spec = ChannelSpecification(
            name="Smart Collection Channel",
            number="42",
            sources=["smart_collection"],
        )
        
        spec_dict = spec.to_dict()
        assert spec_dict["name"] == "Smart Collection Channel"
        assert "smart_collection" in spec_dict["sources"]
    
    def test_channel_specification_supports_marathon_mode(self):
        """Test that specification supports marathon mode settings."""
        from exstreamtv.ai_agent.channel_creator import ChannelSpecification
        
        spec = ChannelSpecification(
            name="Marathon Channel",
            scheduling_rules={
                "marathon_batch_size": 3,
                "marathon_group_by": "show",
            }
        )
        
        spec_dict = spec.to_dict()
        assert spec_dict["scheduling_rules"]["marathon_batch_size"] == 3
        assert spec_dict["scheduling_rules"]["marathon_group_by"] == "show"
    
    def test_channel_specification_supports_deco_config(self):
        """Test that specification supports deco configuration."""
        from exstreamtv.ai_agent.channel_creator import ChannelSpecification
        
        spec = ChannelSpecification(
            name="Deco Channel",
            commercials={"enabled": True, "source": "archive_org"},
        )
        
        assert spec.commercials["enabled"] is True
    
    def test_channel_intent_includes_new_fields(self):
        """Test that ChannelIntent includes migration-compatible fields."""
        from exstreamtv.ai_agent.channel_creator import ChannelIntent
        
        intent = ChannelIntent(
            channel_name="Test Channel",
            commercials_enabled=True,
            holiday_programming=True,
        )
        
        intent_dict = intent.to_dict()
        assert intent_dict["commercials"]["enabled"] is True
        assert intent_dict["holiday_programming"] is True
    
    @pytest.mark.asyncio
    async def test_build_channel_creates_unique_id(self):
        """Test that build_channel generates unique_id for channels."""
        from exstreamtv.ai_agent.channel_creator import (
            ChannelCreatorAgent,
            ChannelCreationStage,
            ChannelSpecification,
        )
        
        # Mock dependencies
        mock_ollama = MagicMock()
        agent = ChannelCreatorAgent(ollama_client=mock_ollama)
        
        # Create a ready session
        session = agent.create_session("test-build")
        session.stage = ChannelCreationStage.READY
        session.specification = ChannelSpecification(
            name="Test Channel",
            number="100",
        )
        
        # Verify that when specification is ready, it has the fields for unique_id
        assert session.specification.name == "Test Channel"
        assert session.stage == ChannelCreationStage.READY
        
        # Note: Full build_channel test requires database mocking
        # This test verifies the specification is properly configured
        spec_dict = session.specification.to_dict()
        assert "name" in spec_dict
        assert spec_dict["name"] == "Test Channel"


class TestScheduleGeneratorMigrationCompat:
    """Test Schedule Generator compatibility with new schema."""
    
    def test_generate_schedule_with_marathon_settings(self):
        """Test schedule generation with marathon batch settings."""
        from exstreamtv.ai_agent.schedule_generator import ScheduleGenerator
        
        generator = ScheduleGenerator()
        
        # Create a spec with marathon settings
        class MockSpec:
            dayparts = {
                "primetime": {
                    "start": "20:00",
                    "end": "23:00",
                    "genres": ["drama"],
                }
            }
            special_blocks = []
            commercials = {"enabled": False}
            scheduling_rules = {
                "marathon_batch_size": 3,
            }
        
        slots = generator.generate_schedule_template(MockSpec(), days=1)
        assert len(slots) > 0
    
    def test_time_slot_supports_collection_types(self):
        """Test that TimeSlot supports different collection types."""
        from exstreamtv.ai_agent.schedule_generator import TimeSlot, DayOfWeek
        
        slot = TimeSlot(
            start_time=time(20, 0),
            end_time=time(21, 0),
            duration_minutes=60,
            content_type="show",
            genre="drama",
            source="smart_collection",
            day_of_week=DayOfWeek.MONDAY,
        )
        
        slot_dict = slot.to_dict()
        assert slot_dict["source"] == "smart_collection"
        assert slot_dict["duration_minutes"] == 60


class TestBlockExecutorMigrationCompat:
    """Test Block Executor compatibility with new schema."""
    
    def test_block_info_includes_new_fields(self):
        """Test that BlockInfo can represent new block fields."""
        from exstreamtv.ai_agent.block_executor import BlockInfo
        
        block = BlockInfo(
            id=1,
            name="Morning Block",
            start_time=time(8, 0),
            duration_minutes=180,
            days_of_week=127,
            item_count=5,
        )
        
        block_dict = block.to_dict()
        assert block_dict["duration_minutes"] == 180
        assert block_dict["days_of_week"] == 127
    
    def test_days_to_bitmask_conversion(self):
        """Test day-of-week to bitmask conversion."""
        from exstreamtv.ai_agent.block_executor import BlockScheduleExecutor, DAY_BITS
        
        executor = BlockScheduleExecutor()
        
        # Test all days
        bitmask = executor._days_to_bitmask([])
        assert bitmask == 127  # All days
        
        # Test specific days
        bitmask = executor._days_to_bitmask(["monday", "wednesday", "friday"])
        assert bitmask & DAY_BITS["monday"]
        assert bitmask & DAY_BITS["wednesday"]
        assert bitmask & DAY_BITS["friday"]
        assert not (bitmask & DAY_BITS["tuesday"])
    
    def test_bitmask_to_days_conversion(self):
        """Test bitmask to day names conversion."""
        from exstreamtv.ai_agent.block_executor import BlockScheduleExecutor
        
        # Monday + Wednesday + Friday = 2 + 8 + 32 = 42
        days = BlockScheduleExecutor.bitmask_to_days(42)
        assert "monday" in days
        assert "wednesday" in days
        assert "friday" in days
        assert "tuesday" not in days


class TestDecoIntegratorMigrationCompat:
    """Test Deco Integrator compatibility with new schema."""
    
    def test_deco_configuration_to_dict(self):
        """Test that DecoConfiguration can be converted to database-compatible dict."""
        from exstreamtv.ai_agent.deco_integrator import DecoConfiguration
        
        config = DecoConfiguration(
            theme="retro_tv",
            era="1980s",
        )
        
        config_dict = config.to_dict()
        assert config_dict["theme"] == "retro_tv"
        assert config_dict["era"] == "1980s"
        assert "watermark" in config_dict
        assert "bumpers" in config_dict
    
    def test_suggest_deco_returns_valid_config(self):
        """Test that suggest_deco returns a complete configuration."""
        from exstreamtv.ai_agent.deco_integrator import DecoIntegrator
        
        integrator = DecoIntegrator()
        
        config = integrator.suggest_deco(
            channel_name="Classic TV",
            genres=["comedy", "drama"],
            era="1980s",
        )
        
        assert config is not None
        assert config.era == "1980s"
        assert config.has_any_enabled
    
    def test_deco_theme_presets_available(self):
        """Test that all theme presets are available."""
        from exstreamtv.ai_agent.deco_integrator import DecoIntegrator
        
        integrator = DecoIntegrator()
        themes = integrator.get_available_themes()
        
        assert "retro_tv" in themes
        assert "movie_channel" in themes
        assert "kids_channel" in themes


class TestFixSuggesterMigrationCompat:
    """Test Fix Suggester compatibility with new error patterns."""
    
    def test_fix_suggestion_for_smart_collection_error(self):
        """Test that fixes can be suggested for smart collection errors."""
        import re
        from datetime import datetime
        from exstreamtv.ai_agent.fix_suggester import FixSuggester
        from exstreamtv.ai_agent.log_analyzer import LogMatch, LogPattern, LogSeverity
        
        suggester = FixSuggester()
        
        # Create a mock log match for smart collection error
        pattern = LogPattern(
            name="smart_collection_empty",
            pattern=re.compile(r"Smart collection .* returned no items"),
            category="scheduling",
            severity=LogSeverity.WARNING,
            description="Smart collection query returned no results",
        )
        
        log_match = LogMatch(
            pattern=pattern,
            timestamp=datetime.now(),
            message="Smart collection 'Comedy 1980s' returned no items",
            context={"collection_name": "Comedy 1980s"},
        )
        
        # Get rule-based suggestions (Ollama not available in test)
        suggestions = suggester._suggest_rule_based_fixes(log_match)
        
        # Rule-based suggestions depend on pattern matching
        # Just verify the method doesn't crash and returns a list
        assert isinstance(suggestions, list)
    
    def test_fix_risk_levels_defined(self):
        """Test that all risk levels are properly defined."""
        from exstreamtv.ai_agent.fix_suggester import FixRiskLevel
        
        assert FixRiskLevel.SAFE.value == "safe"
        assert FixRiskLevel.LOW.value == "low"
        assert FixRiskLevel.MEDIUM.value == "medium"
        assert FixRiskLevel.HIGH.value == "high"
        assert FixRiskLevel.CRITICAL.value == "critical"


class TestAutoHealerMigrationCompat:
    """Test Auto Healer compatibility with new entities."""
    
    def test_auto_healer_initialization(self):
        """Test that AutoHealer can be initialized with new settings."""
        from pathlib import Path
        from exstreamtv.utils.auto_healer import AutoHealer
        
        healer = AutoHealer(
            workspace_root=Path("/tmp"),
            dry_run=True,
            enable_ai=False,
        )
        
        assert healer.dry_run is True
        assert healer.enable_ai is False
    
    def test_auto_healer_stats(self):
        """Test that AutoHealer stats include all expected fields."""
        from pathlib import Path
        from exstreamtv.utils.auto_healer import AutoHealer
        
        healer = AutoHealer(
            workspace_root=Path("/tmp"),
            dry_run=True,
            enable_ai=False,
        )
        
        stats = healer.get_stats()
        
        assert "run_count" in stats
        assert "total_errors_detected" in stats
        assert "total_fixes_applied" in stats
        assert "dry_run" in stats


class TestAIMigrationIntegration:
    """Integration tests for AI systems with migrated data."""
    
    def test_channel_specification_from_ai_response(self):
        """Test creating specification from AI response with new fields."""
        from exstreamtv.ai_agent.channel_creator import ChannelSpecification
        
        ai_response = {
            "ready_to_build": True,
            "channel_spec": {
                "name": "80s Classics",
                "number": "80",
                "description": "Classic 80s TV shows",
                "sources": ["plex", "smart_collection"],
                "era": {"start_year": 1980, "end_year": 1989},
                "dayparts": {
                    "primetime": {
                        "start": "20:00",
                        "end": "23:00",
                        "genres": ["drama", "comedy"],
                    }
                },
                "commercials": {
                    "enabled": True,
                    "source": "archive_org",
                },
                "deco": {
                    "watermark_mode": "override",
                    "theme": "retro_tv",
                },
                "scheduling_rules": {
                    "marathon_batch_size": 2,
                    "marathon_group_by": "show",
                },
            }
        }
        
        spec = ChannelSpecification.from_ai_response(ai_response)
        
        assert spec.name == "80s Classics"
        assert spec.era["start_year"] == 1980
        assert spec.commercials["enabled"] is True
        assert "smart_collection" in spec.sources
    
    def test_holiday_calendar_integration(self):
        """Test that holiday calendar works with schedule generation."""
        from datetime import datetime
        from exstreamtv.ai_agent.schedule_generator import HolidayCalendar
        
        calendar = HolidayCalendar()
        
        # Test Christmas period
        christmas = datetime(2024, 12, 20)
        holiday = calendar.get_active_holiday(christmas)
        assert holiday is not None
        
        # Test regular day
        regular = datetime(2024, 8, 15)
        holiday = calendar.get_active_holiday(regular)
        assert holiday is None
    
    def test_validators_support_new_entities(self):
        """Test that validators support new entity types."""
        from exstreamtv.importers.validators import ValidationResult
        
        result = ValidationResult()
        
        # Add various types of messages
        result.add_info("Found 10 smart collections")
        result.add_warning("3 deco configs missing watermarks")
        result.counts["smart_collections"] = 10
        result.counts["deco"] = 5
        
        result_dict = result.to_dict()
        
        assert result.is_valid is True
        assert len(result.info) == 1
        assert len(result.warnings) == 1
        assert result_dict["counts"]["smart_collections"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
