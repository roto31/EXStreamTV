"""
Conversation Manager for AI Channel Creation

Manages multi-turn conversations with session storage, history tracking,
and context aggregation for Ollama prompts.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ConversationConfig:
    """Configuration for conversation management."""
    
    # Session timeout in seconds (default 1 hour)
    session_timeout_seconds: int = 3600
    
    # Maximum messages per session
    max_messages: int = 100
    
    # Maximum context length for AI prompts (in characters)
    max_context_length: int = 8000
    
    # Cleanup interval in seconds
    cleanup_interval_seconds: int = 300
    
    # Enable Redis storage (if False, uses in-memory only)
    use_redis: bool = False
    redis_url: str = "redis://localhost:6379"
    redis_prefix: str = "exstreamtv:conversation:"


@dataclass
class Message:
    """A single conversation message."""
    
    role: str  # "user", "assistant", or "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create from dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow(),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConversationSession:
    """A conversation session with message history."""
    
    session_id: str
    messages: list[Message] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    
    # Session state
    is_active: bool = True
    
    def add_message(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Add a message to the conversation."""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        return message
    
    def get_history(
        self,
        max_messages: int | None = None,
        max_length: int | None = None,
    ) -> list[dict[str, str]]:
        """
        Get conversation history for AI prompt.
        
        Args:
            max_messages: Maximum number of messages to include
            max_length: Maximum total character length
            
        Returns:
            List of message dicts with role and content
        """
        messages = self.messages
        
        # Limit by count
        if max_messages and len(messages) > max_messages:
            messages = messages[-max_messages:]
        
        # Build history
        history = []
        total_length = 0
        
        for msg in reversed(messages):
            msg_dict = {"role": msg.role, "content": msg.content}
            msg_length = len(msg.content)
            
            if max_length and total_length + msg_length > max_length:
                break
            
            history.insert(0, msg_dict)
            total_length += msg_length
        
        return history
    
    def get_last_message(self, role: str | None = None) -> Message | None:
        """Get the last message, optionally filtered by role."""
        for msg in reversed(self.messages):
            if role is None or msg.role == role:
                return msg
        return None
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationSession":
        """Create from dictionary."""
        session = cls(
            session_id=data["session_id"],
            context=data.get("context", {}),
            is_active=data.get("is_active", True),
        )
        
        session.messages = [
            Message.from_dict(msg) for msg in data.get("messages", [])
        ]
        
        if data.get("created_at"):
            session.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            session.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("expires_at"):
            session.expires_at = datetime.fromisoformat(data["expires_at"])
        
        return session


class ConversationManager:
    """
    Manages conversation sessions for AI interactions.
    
    Provides session storage, history tracking, and context management
    for multi-turn conversations with Ollama.
    """
    
    def __init__(self, config: ConversationConfig | None = None):
        """
        Initialize conversation manager.
        
        Args:
            config: Optional configuration
        """
        self.config = config or ConversationConfig()
        
        # In-memory session storage
        self._sessions: dict[str, ConversationSession] = {}
        
        # Redis client (optional)
        self._redis: Any = None
        
        # Cleanup task
        self._cleanup_task: asyncio.Task | None = None
        
        # Event callbacks
        self._on_session_created: list[Callable] = []
        self._on_session_expired: list[Callable] = []
        self._on_message_added: list[Callable] = []
    
    async def start(self) -> None:
        """Start the conversation manager."""
        # Initialize Redis if configured
        if self.config.use_redis:
            await self._init_redis()
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("ConversationManager started")
    
    async def stop(self) -> None:
        """Stop the conversation manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._redis:
            await self._redis.close()
        
        logger.info("ConversationManager stopped")
    
    async def _init_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis.asyncio as redis
            
            self._redis = redis.from_url(self.config.redis_url)
            await self._redis.ping()
            logger.info("Connected to Redis for conversation storage")
            
        except ImportError:
            logger.warning("redis package not installed, using in-memory storage")
            self.config.use_redis = False
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}, using in-memory storage")
            self.config.use_redis = False
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval_seconds)
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in cleanup loop: {e}")
    
    def create_session(
        self,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> ConversationSession:
        """
        Create a new conversation session.
        
        Args:
            session_id: Optional custom session ID
            context: Optional initial context
            timeout_seconds: Optional custom timeout
            
        Returns:
            New ConversationSession
        """
        import uuid
        
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        timeout = timeout_seconds or self.config.session_timeout_seconds
        
        session = ConversationSession(
            session_id=session_id,
            context=context or {},
            expires_at=datetime.utcnow() + timedelta(seconds=timeout),
        )
        
        self._sessions[session_id] = session
        
        # Trigger callbacks
        for callback in self._on_session_created:
            try:
                callback(session)
            except Exception as e:
                logger.warning(f"Error in session created callback: {e}")
        
        logger.debug(f"Created conversation session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> ConversationSession | None:
        """
        Get an existing session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            ConversationSession or None if not found/expired
        """
        session = self._sessions.get(session_id)
        
        if session and session.is_expired():
            # Clean up expired session
            self.delete_session(session_id)
            return None
        
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if session was deleted
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.is_active = False
            del self._sessions[session_id]
            
            # Trigger callbacks
            for callback in self._on_session_expired:
                try:
                    callback(session)
                except Exception as e:
                    logger.warning(f"Error in session expired callback: {e}")
            
            logger.debug(f"Deleted conversation session: {session_id}")
            return True
        
        return False
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message | None:
        """
        Add a message to a session.
        
        Args:
            session_id: Session ID
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Added Message or None if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        # Check message limit
        if len(session.messages) >= self.config.max_messages:
            # Remove oldest messages
            excess = len(session.messages) - self.config.max_messages + 1
            session.messages = session.messages[excess:]
        
        message = session.add_message(role, content, metadata)
        
        # Reset expiration
        session.expires_at = datetime.utcnow() + timedelta(
            seconds=self.config.session_timeout_seconds
        )
        
        # Trigger callbacks
        for callback in self._on_message_added:
            try:
                callback(session, message)
            except Exception as e:
                logger.warning(f"Error in message added callback: {e}")
        
        return message
    
    def get_conversation_context(
        self,
        session_id: str,
        max_messages: int | None = None,
        max_length: int | None = None,
        include_system: bool = True,
    ) -> str:
        """
        Build conversation context for AI prompt.
        
        Args:
            session_id: Session ID
            max_messages: Maximum messages to include
            max_length: Maximum context length
            include_system: Include system messages
            
        Returns:
            Formatted conversation context string
        """
        session = self.get_session(session_id)
        if not session:
            return ""
        
        max_len = max_length or self.config.max_context_length
        history = session.get_history(max_messages, max_len)
        
        if not include_system:
            history = [msg for msg in history if msg["role"] != "system"]
        
        # Format as conversation
        lines = []
        for msg in history:
            role_label = {
                "user": "User",
                "assistant": "Assistant",
                "system": "System",
            }.get(msg["role"], msg["role"].capitalize())
            
            lines.append(f"{role_label}: {msg['content']}")
        
        return "\n\n".join(lines)
    
    def update_context(
        self,
        session_id: str,
        context_updates: dict[str, Any],
    ) -> bool:
        """
        Update session context.
        
        Args:
            session_id: Session ID
            context_updates: Dict of context updates
            
        Returns:
            True if session was updated
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.context.update(context_updates)
        session.updated_at = datetime.utcnow()
        return True
    
    def list_sessions(
        self,
        include_expired: bool = False,
    ) -> list[dict[str, Any]]:
        """
        List all sessions.
        
        Args:
            include_expired: Include expired sessions
            
        Returns:
            List of session info dicts
        """
        sessions = []
        
        for session_id, session in self._sessions.items():
            if not include_expired and session.is_expired():
                continue
            
            sessions.append({
                "session_id": session_id,
                "message_count": len(session.messages),
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                "is_active": session.is_active,
            })
        
        return sessions
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.is_expired()
        ]
        
        for session_id in expired_ids:
            self.delete_session(session_id)
        
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired conversation sessions")
        
        return len(expired_ids)
    
    def on_session_created(self, callback: Callable) -> None:
        """Register callback for session creation."""
        self._on_session_created.append(callback)
    
    def on_session_expired(self, callback: Callable) -> None:
        """Register callback for session expiration."""
        self._on_session_expired.append(callback)
    
    def on_message_added(self, callback: Callable) -> None:
        """Register callback for message addition."""
        self._on_message_added.append(callback)
    
    async def save_to_redis(self, session: ConversationSession) -> bool:
        """Save session to Redis."""
        if not self._redis:
            return False
        
        try:
            import json
            
            key = f"{self.config.redis_prefix}{session.session_id}"
            data = json.dumps(session.to_dict())
            
            ttl = self.config.session_timeout_seconds
            await self._redis.setex(key, ttl, data)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error saving session to Redis: {e}")
            return False
    
    async def load_from_redis(self, session_id: str) -> ConversationSession | None:
        """Load session from Redis."""
        if not self._redis:
            return None
        
        try:
            import json
            
            key = f"{self.config.redis_prefix}{session_id}"
            data = await self._redis.get(key)
            
            if data:
                session_dict = json.loads(data)
                session = ConversationSession.from_dict(session_dict)
                
                # Also store in memory
                self._sessions[session_id] = session
                
                return session
            
            return None
            
        except Exception as e:
            logger.exception(f"Error loading session from Redis: {e}")
            return None


# Singleton instance for convenience
_manager: ConversationManager | None = None


def get_conversation_manager() -> ConversationManager:
    """Get the global conversation manager instance."""
    global _manager
    if _manager is None:
        _manager = ConversationManager()
    return _manager


def set_conversation_manager(manager: ConversationManager) -> None:
    """Set the global conversation manager instance."""
    global _manager
    _manager = manager
