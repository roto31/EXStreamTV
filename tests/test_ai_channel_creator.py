"""
Tests for the AI Channel Creator functionality.

Tests the channel creation conversation flow, schedule generation,
and media aggregation components.
"""

import asyncio
import json
import pytest
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestTVExecutivePrompts:
    """Test the TV Executive persona prompts."""
    
    def test_persona_prompt_exists(self):
        """Test that the persona prompt is defined."""
        from exstreamtv.ai_agent.prompts.tv_executive import TV_EXECUTIVE_PERSONA
        
        assert TV_EXECUTIVE_PERSONA
        assert "television programming executive" in TV_EXECUTIVE_PERSONA.lower()
        assert "1970s" in TV_EXECUTIVE_PERSONA or "1980s" in TV_EXECUTIVE_PERSONA
    
    def test_system_prompt_contains_json_format(self):
        """Test that the system prompt includes JSON specification format."""
        from exstreamtv.ai_agent.prompts.tv_executive import TV_EXECUTIVE_SYSTEM_PROMPT
        
        assert "ready_to_build" in TV_EXECUTIVE_SYSTEM_PROMPT
        assert "channel_spec" in TV_EXECUTIVE_SYSTEM_PROMPT
        assert "dayparts" in TV_EXECUTIVE_SYSTEM_PROMPT
    
    def test_build_channel_creation_prompt(self):
        """Test building a channel creation prompt."""
        from exstreamtv.ai_agent.prompts.tv_executive import build_channel_creation_prompt
        
        prompt = build_channel_creation_prompt(
            user_message="I want a 1970s TV channel",
            conversation_history=[
                {"role": "assistant", "content": "Hello!"},
                {"role": "user", "content": "Hi there"},
            ],
        )
        
        assert "I want a 1970s TV channel" in prompt
        assert "CONVERSATION HISTORY" in prompt
        assert "Max Sterling" in prompt


class TestChannelCreatorAgent:
    """Test the ChannelCreatorAgent class."""
    
    def test_create_session(self):
        """Test creating a new session."""
        from exstreamtv.ai_agent.channel_creator import ChannelCreatorAgent
        
        mock_ollama = MagicMock()
        agent = ChannelCreatorAgent(ollama_client=mock_ollama)
        
        session = agent.create_session()
        
        assert session is not None
        assert session.session_id
        assert len(session.messages) == 0
    
    def test_session_management(self):
        """Test session creation, retrieval, and deletion."""
        from exstreamtv.ai_agent.channel_creator import ChannelCreatorAgent
        
        mock_ollama = MagicMock()
        agent = ChannelCreatorAgent(ollama_client=mock_ollama)
        
        # Create session
        session = agent.create_session(session_id="test-123")
        assert session.session_id == "test-123"
        
        # Retrieve session
        retrieved = agent.get_session("test-123")
        assert retrieved is not None
        assert retrieved.session_id == "test-123"
        
        # List sessions
        sessions = agent.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "test-123"
        
        # Delete session
        deleted = agent.delete_session("test-123")
        assert deleted is True
        
        # Verify deleted
        assert agent.get_session("test-123") is None
    
    def test_extract_specification(self):
        """Test extracting JSON specification from AI response."""
        from exstreamtv.ai_agent.channel_creator import ChannelCreatorAgent
        
        mock_ollama = MagicMock()
        agent = ChannelCreatorAgent(ollama_client=mock_ollama)
        
        response = '''
        Here's a great channel for you!
        
        ```json
        {
            "ready_to_build": true,
            "channel_spec": {
                "name": "Classic TV",
                "sources": ["plex"],
                "dayparts": {
                    "primetime": {"start": "20:00", "end": "23:00"}
                }
            }
        }
        ```
        '''
        
        spec = agent._extract_specification(response)
        
        assert spec is not None
        assert spec["ready_to_build"] is True
        assert spec["channel_spec"]["name"] == "Classic TV"
    
    @pytest.mark.asyncio
    async def test_get_welcome_message(self):
        """Test getting the welcome message."""
        from exstreamtv.ai_agent.channel_creator import ChannelCreatorAgent
        
        mock_ollama = MagicMock()
        agent = ChannelCreatorAgent(ollama_client=mock_ollama)
        
        welcome = await agent.get_welcome_message()
        
        assert welcome
        assert "Max Sterling" in welcome or "programming" in welcome.lower()


class TestConversationManager:
    """Test the ConversationManager class."""
    
    def test_create_session(self):
        """Test creating a conversation session."""
        from exstreamtv.ai_agent.conversation import ConversationManager
        
        manager = ConversationManager()
        session = manager.create_session()
        
        assert session is not None
        assert session.session_id
        assert session.is_active
    
    def test_add_message(self):
        """Test adding messages to a session."""
        from exstreamtv.ai_agent.conversation import ConversationManager
        
        manager = ConversationManager()
        session = manager.create_session()
        
        message = manager.add_message(
            session.session_id,
            "user",
            "Hello, I want a TV channel",
        )
        
        assert message is not None
        assert message.role == "user"
        assert message.content == "Hello, I want a TV channel"
        
        # Check session has the message
        retrieved = manager.get_session(session.session_id)
        assert len(retrieved.messages) == 1
    
    def test_get_conversation_context(self):
        """Test building conversation context."""
        from exstreamtv.ai_agent.conversation import ConversationManager
        
        manager = ConversationManager()
        session = manager.create_session()
        
        manager.add_message(session.session_id, "user", "I want a channel")
        manager.add_message(session.session_id, "assistant", "What kind?")
        manager.add_message(session.session_id, "user", "Classic TV")
        
        context = manager.get_conversation_context(session.session_id)
        
        assert "I want a channel" in context
        assert "What kind?" in context
        assert "Classic TV" in context


class TestScheduleGenerator:
    """Test the ScheduleGenerator class."""
    
    def test_parse_time(self):
        """Test parsing time strings."""
        from exstreamtv.ai_agent.schedule_generator import ScheduleGenerator
        
        generator = ScheduleGenerator()
        
        t = generator._parse_time("20:00")
        assert t.hour == 20
        assert t.minute == 0
        
        t = generator._parse_time("08:30")
        assert t.hour == 8
        assert t.minute == 30
    
    def test_generate_daypart_slots(self):
        """Test generating slots for a daypart."""
        from exstreamtv.ai_agent.schedule_generator import ScheduleGenerator, DayOfWeek
        
        generator = ScheduleGenerator()
        
        slots = generator._generate_daypart_slots(
            start_time=time(20, 0),
            end_time=time(23, 0),
            genres=["drama", "comedy"],
            day_of_week=DayOfWeek.MONDAY,
            commercials_enabled=True,
        )
        
        assert len(slots) > 0
        
        # Check slots are within time range
        for slot in slots:
            assert slot.start_time >= time(20, 0)
            assert slot.day_of_week == DayOfWeek.MONDAY
    
    def test_holiday_calendar(self):
        """Test the holiday calendar."""
        from exstreamtv.ai_agent.schedule_generator import HolidayCalendar
        
        calendar = HolidayCalendar()
        
        # Test Christmas
        christmas = datetime(2024, 12, 15)
        holiday = calendar.get_active_holiday(christmas)
        assert holiday is not None
        assert "Christmas" in holiday.name or "Holiday" in holiday.name
        
        # Test regular day
        regular = datetime(2024, 6, 15)
        holiday = calendar.get_active_holiday(regular)
        assert holiday is None


class TestMediaAggregator:
    """Test the MediaAggregator class."""
    
    @pytest.mark.asyncio
    async def test_get_available_sources_no_clients(self):
        """Test getting sources with no clients configured."""
        from exstreamtv.ai_agent.media_aggregator import MediaAggregator
        
        aggregator = MediaAggregator()
        sources = await aggregator.get_available_sources()
        
        # Should have archive_org available (public)
        assert "archive_org" in sources
        assert sources["archive_org"]["available"] is True
    
    @pytest.mark.asyncio
    async def test_search_returns_empty_without_clients(self):
        """Test search returns empty results without clients."""
        from exstreamtv.ai_agent.media_aggregator import MediaAggregator
        
        aggregator = MediaAggregator()
        results = await aggregator.search(
            query="classic tv",
            sources=["plex"],  # No Plex client configured
        )
        
        # Should return empty dict since no clients available
        assert "plex" not in results or not results.get("plex")


class TestChannelSpecification:
    """Test the ChannelSpecification class."""
    
    def test_from_ai_response(self):
        """Test creating specification from AI response."""
        from exstreamtv.ai_agent.channel_creator import ChannelSpecification
        
        ai_response = {
            "ready_to_build": True,
            "channel_spec": {
                "name": "Retro TV",
                "number": "42",
                "description": "Classic television",
                "sources": ["plex", "archive_org"],
                "era": {"start_year": 1970, "end_year": 1989},
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
            }
        }
        
        spec = ChannelSpecification.from_ai_response(ai_response)
        
        assert spec.name == "Retro TV"
        assert spec.number == "42"
        assert "plex" in spec.sources
        assert spec.era["start_year"] == 1970
        assert spec.commercials["enabled"] is True
    
    def test_to_dict(self):
        """Test converting specification to dict."""
        from exstreamtv.ai_agent.channel_creator import ChannelSpecification
        
        spec = ChannelSpecification(
            name="Test Channel",
            number="100",
            sources=["plex"],
        )
        
        d = spec.to_dict()
        
        assert d["name"] == "Test Channel"
        assert d["number"] == "100"
        assert "plex" in d["sources"]


class TestChannelIntent:
    """Test the ChannelIntent class."""
    
    def test_default_values(self):
        """Test default intent values."""
        from exstreamtv.ai_agent.channel_creator import ChannelIntent
        
        intent = ChannelIntent()
        
        assert intent.channel_name is None
        assert intent.is_24_hour is True
        assert intent.commercials_enabled is False
        assert intent.chronological_episodes is True
    
    def test_to_dict(self):
        """Test converting intent to dict."""
        from exstreamtv.ai_agent.channel_creator import ChannelIntent
        
        intent = ChannelIntent(
            channel_name="Classic Movies",
            use_plex=True,
            genres=["action", "drama"],
            commercials_enabled=True,
        )
        
        d = intent.to_dict()
        
        assert d["channel_name"] == "Classic Movies"
        assert d["sources"]["plex"] is True
        assert "action" in d["genres"]
        assert d["commercials"]["enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
