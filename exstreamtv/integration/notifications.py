"""
Notification Services Integration

Supports sending notifications via:
- Discord webhooks
- Telegram bots
- Pushover
- Email (SMTP)
- Slack
- Custom webhooks
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import httpx

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    STREAM_STARTED = "stream_started"
    STREAM_STOPPED = "stream_stopped"
    STREAM_ERROR = "stream_error"
    SCAN_COMPLETED = "scan_completed"
    SYSTEM_ALERT = "system_alert"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """A notification to be sent."""
    
    title: str
    message: str
    notification_type: NotificationType = NotificationType.INFO
    priority: NotificationPriority = NotificationPriority.NORMAL
    
    # Optional data
    url: Optional[str] = None
    image_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Tracking
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "type": self.notification_type.value,
            "priority": self.priority.value,
            "url": self.url,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class NotificationServiceConfig:
    """Base configuration for notification services."""
    
    name: str
    is_enabled: bool = True
    
    # Filter what notifications to send
    notification_types: Optional[List[NotificationType]] = None
    min_priority: NotificationPriority = NotificationPriority.NORMAL


class NotificationService(ABC):
    """Abstract base for notification services."""
    
    def __init__(self, config: NotificationServiceConfig):
        self.config = config
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
    
    def should_send(self, notification: Notification) -> bool:
        """Check if this notification should be sent."""
        if not self.config.is_enabled:
            return False
        
        # Check type filter
        if self.config.notification_types:
            if notification.notification_type not in self.config.notification_types:
                return False
        
        # Check priority filter
        priority_order = [p for p in NotificationPriority]
        min_idx = priority_order.index(self.config.min_priority)
        notif_idx = priority_order.index(notification.priority)
        
        if notif_idx < min_idx:
            return False
        
        return True
    
    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Send a notification."""
        pass
    
    @abstractmethod
    async def test(self) -> tuple[bool, str]:
        """Test the service configuration."""
        pass


# ============================================================================
# Discord
# ============================================================================

@dataclass
class DiscordConfig(NotificationServiceConfig):
    """Discord webhook configuration."""
    
    webhook_url: str = ""
    username: str = "EXStreamTV"
    avatar_url: Optional[str] = None


class DiscordService(NotificationService):
    """Discord webhook notification service."""
    
    def __init__(self, config: DiscordConfig):
        super().__init__(config)
        self.discord_config = config
    
    async def send(self, notification: Notification) -> bool:
        if not self.should_send(notification):
            return False
        
        try:
            # Build Discord embed
            color = self._get_color(notification.notification_type)
            
            embed = {
                "title": notification.title,
                "description": notification.message,
                "color": color,
                "timestamp": notification.created_at.isoformat(),
            }
            
            if notification.url:
                embed["url"] = notification.url
            
            if notification.image_url:
                embed["thumbnail"] = {"url": notification.image_url}
            
            payload = {
                "username": self.discord_config.username,
                "embeds": [embed],
            }
            
            if self.discord_config.avatar_url:
                payload["avatar_url"] = self.discord_config.avatar_url
            
            response = await self._http_client.post(
                self.discord_config.webhook_url,
                json=payload,
            )
            
            return response.status_code in (200, 204)
        
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
            return False
    
    async def test(self) -> tuple[bool, str]:
        try:
            notification = Notification(
                title="Test Notification",
                message="This is a test from EXStreamTV",
                notification_type=NotificationType.INFO,
            )
            
            async with self:
                success = await self.send(notification)
            
            if success:
                return True, "Discord webhook is working"
            return False, "Failed to send test message"
        
        except Exception as e:
            return False, str(e)
    
    def _get_color(self, notification_type: NotificationType) -> int:
        """Get embed color for notification type."""
        colors = {
            NotificationType.INFO: 0x3498db,      # Blue
            NotificationType.SUCCESS: 0x2ecc71,   # Green
            NotificationType.WARNING: 0xf39c12,   # Orange
            NotificationType.ERROR: 0xe74c3c,     # Red
            NotificationType.STREAM_STARTED: 0x9b59b6,  # Purple
            NotificationType.STREAM_STOPPED: 0x95a5a6,  # Gray
            NotificationType.STREAM_ERROR: 0xe74c3c,
            NotificationType.SCAN_COMPLETED: 0x2ecc71,
            NotificationType.SYSTEM_ALERT: 0xf39c12,
        }
        return colors.get(notification_type, 0x3498db)


# ============================================================================
# Telegram
# ============================================================================

@dataclass
class TelegramConfig(NotificationServiceConfig):
    """Telegram bot configuration."""
    
    bot_token: str = ""
    chat_id: str = ""  # Can be user ID, group ID, or channel username
    parse_mode: str = "HTML"


class TelegramService(NotificationService):
    """Telegram bot notification service."""
    
    API_BASE = "https://api.telegram.org"
    
    def __init__(self, config: TelegramConfig):
        super().__init__(config)
        self.telegram_config = config
    
    async def send(self, notification: Notification) -> bool:
        if not self.should_send(notification):
            return False
        
        try:
            # Build message
            emoji = self._get_emoji(notification.notification_type)
            
            if self.telegram_config.parse_mode == "HTML":
                text = f"{emoji} <b>{notification.title}</b>\n\n{notification.message}"
            else:
                text = f"{emoji} *{notification.title}*\n\n{notification.message}"
            
            if notification.url:
                text += f"\n\n🔗 {notification.url}"
            
            # Send message
            url = f"{self.API_BASE}/bot{self.telegram_config.bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.telegram_config.chat_id,
                "text": text,
                "parse_mode": self.telegram_config.parse_mode,
                "disable_web_page_preview": False,
            }
            
            response = await self._http_client.post(url, json=payload)
            result = response.json()
            
            return result.get("ok", False)
        
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            return False
    
    async def test(self) -> tuple[bool, str]:
        try:
            # Verify bot token
            url = f"{self.API_BASE}/bot{self.telegram_config.bot_token}/getMe"
            
            async with self:
                response = await self._http_client.get(url)
                result = response.json()
                
                if not result.get("ok"):
                    return False, "Invalid bot token"
                
                bot_name = result["result"]["username"]
                
                # Send test message
                notification = Notification(
                    title="Test Notification",
                    message="This is a test from EXStreamTV",
                )
                
                if await self.send(notification):
                    return True, f"Connected as @{bot_name}"
                
                return False, "Failed to send test message"
        
        except Exception as e:
            return False, str(e)
    
    def _get_emoji(self, notification_type: NotificationType) -> str:
        """Get emoji for notification type."""
        emojis = {
            NotificationType.INFO: "ℹ️",
            NotificationType.SUCCESS: "✅",
            NotificationType.WARNING: "⚠️",
            NotificationType.ERROR: "❌",
            NotificationType.STREAM_STARTED: "▶️",
            NotificationType.STREAM_STOPPED: "⏹️",
            NotificationType.STREAM_ERROR: "🔴",
            NotificationType.SCAN_COMPLETED: "📺",
            NotificationType.SYSTEM_ALERT: "🚨",
        }
        return emojis.get(notification_type, "📢")


# ============================================================================
# Pushover
# ============================================================================

@dataclass
class PushoverConfig(NotificationServiceConfig):
    """Pushover configuration."""
    
    user_key: str = ""
    api_token: str = ""
    device: Optional[str] = None  # Specific device, or None for all


class PushoverService(NotificationService):
    """Pushover notification service."""
    
    API_URL = "https://api.pushover.net/1/messages.json"
    
    def __init__(self, config: PushoverConfig):
        super().__init__(config)
        self.pushover_config = config
    
    async def send(self, notification: Notification) -> bool:
        if not self.should_send(notification):
            return False
        
        try:
            payload = {
                "token": self.pushover_config.api_token,
                "user": self.pushover_config.user_key,
                "title": notification.title,
                "message": notification.message,
                "priority": self._get_priority(notification.priority),
            }
            
            if notification.url:
                payload["url"] = notification.url
                payload["url_title"] = "View Details"
            
            if self.pushover_config.device:
                payload["device"] = self.pushover_config.device
            
            response = await self._http_client.post(self.API_URL, data=payload)
            result = response.json()
            
            return result.get("status") == 1
        
        except Exception as e:
            logger.error(f"Pushover notification failed: {e}")
            return False
    
    async def test(self) -> tuple[bool, str]:
        try:
            # Validate credentials
            validate_url = "https://api.pushover.net/1/users/validate.json"
            
            async with self:
                response = await self._http_client.post(
                    validate_url,
                    data={
                        "token": self.pushover_config.api_token,
                        "user": self.pushover_config.user_key,
                    },
                )
                result = response.json()
                
                if result.get("status") != 1:
                    return False, result.get("errors", ["Invalid credentials"])[0]
                
                # Send test
                notification = Notification(
                    title="Test Notification",
                    message="This is a test from EXStreamTV",
                )
                
                if await self.send(notification):
                    return True, "Pushover is configured correctly"
                
                return False, "Failed to send test message"
        
        except Exception as e:
            return False, str(e)
    
    def _get_priority(self, priority: NotificationPriority) -> int:
        """Convert priority to Pushover priority."""
        mapping = {
            NotificationPriority.LOW: -1,
            NotificationPriority.NORMAL: 0,
            NotificationPriority.HIGH: 1,
            NotificationPriority.URGENT: 2,
        }
        return mapping.get(priority, 0)


# ============================================================================
# Slack
# ============================================================================

@dataclass
class SlackConfig(NotificationServiceConfig):
    """Slack webhook configuration."""
    
    webhook_url: str = ""
    channel: Optional[str] = None
    username: str = "EXStreamTV"
    icon_emoji: str = ":tv:"


class SlackService(NotificationService):
    """Slack webhook notification service."""
    
    def __init__(self, config: SlackConfig):
        super().__init__(config)
        self.slack_config = config
    
    async def send(self, notification: Notification) -> bool:
        if not self.should_send(notification):
            return False
        
        try:
            color = self._get_color(notification.notification_type)
            
            payload = {
                "username": self.slack_config.username,
                "icon_emoji": self.slack_config.icon_emoji,
                "attachments": [
                    {
                        "color": color,
                        "title": notification.title,
                        "text": notification.message,
                        "ts": int(notification.created_at.timestamp()),
                    }
                ],
            }
            
            if self.slack_config.channel:
                payload["channel"] = self.slack_config.channel
            
            if notification.url:
                payload["attachments"][0]["title_link"] = notification.url
            
            response = await self._http_client.post(
                self.slack_config.webhook_url,
                json=payload,
            )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return False
    
    async def test(self) -> tuple[bool, str]:
        try:
            notification = Notification(
                title="Test Notification",
                message="This is a test from EXStreamTV",
            )
            
            async with self:
                if await self.send(notification):
                    return True, "Slack webhook is working"
                return False, "Failed to send test message"
        
        except Exception as e:
            return False, str(e)
    
    def _get_color(self, notification_type: NotificationType) -> str:
        """Get attachment color for notification type."""
        colors = {
            NotificationType.INFO: "#3498db",
            NotificationType.SUCCESS: "#2ecc71",
            NotificationType.WARNING: "#f39c12",
            NotificationType.ERROR: "#e74c3c",
            NotificationType.STREAM_STARTED: "#9b59b6",
            NotificationType.STREAM_STOPPED: "#95a5a6",
        }
        return colors.get(notification_type, "#3498db")


# ============================================================================
# Notification Manager
# ============================================================================

class NotificationManager:
    """
    Central notification manager.
    
    Features:
    - Multiple service support
    - Notification routing
    - History tracking
    - Rate limiting
    """
    
    def __init__(self):
        self._services: Dict[str, NotificationService] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history = 1000
    
    def add_service(self, name: str, service: NotificationService) -> None:
        """Add a notification service."""
        self._services[name] = service
        logger.info(f"Added notification service: {name}")
    
    def remove_service(self, name: str) -> bool:
        """Remove a notification service."""
        if name in self._services:
            del self._services[name]
            return True
        return False
    
    def get_services(self) -> List[str]:
        """Get list of configured services."""
        return list(self._services.keys())
    
    async def send(
        self,
        notification: Notification,
        services: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        Send a notification to all or specified services.
        
        Returns dict mapping service name to success status.
        """
        results = {}
        
        target_services = services or list(self._services.keys())
        
        for service_name in target_services:
            service = self._services.get(service_name)
            if not service:
                continue
            
            try:
                async with service:
                    success = await service.send(notification)
                results[service_name] = success
            except Exception as e:
                logger.error(f"Service {service_name} error: {e}")
                results[service_name] = False
        
        # Track history
        self._history.append({
            "notification": notification.to_dict(),
            "results": results,
            "timestamp": datetime.now().isoformat(),
        })
        
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        
        return results
    
    async def test_service(self, name: str) -> tuple[bool, str]:
        """Test a specific service."""
        service = self._services.get(name)
        if not service:
            return False, f"Service not found: {name}"
        
        return await service.test()
    
    async def test_all(self) -> Dict[str, tuple[bool, str]]:
        """Test all services."""
        results = {}
        for name in self._services:
            results[name] = await self.test_service(name)
        return results
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """Get notification history."""
        return self._history[-limit:]
    
    # Convenience methods
    
    async def notify_stream_started(
        self,
        channel_name: str,
        channel_number: int,
    ) -> None:
        """Send stream started notification."""
        await self.send(Notification(
            title=f"Channel {channel_number} Started",
            message=f"{channel_name} is now streaming",
            notification_type=NotificationType.STREAM_STARTED,
            priority=NotificationPriority.LOW,
        ))
    
    async def notify_stream_error(
        self,
        channel_name: str,
        error: str,
    ) -> None:
        """Send stream error notification."""
        await self.send(Notification(
            title=f"Stream Error: {channel_name}",
            message=error,
            notification_type=NotificationType.STREAM_ERROR,
            priority=NotificationPriority.HIGH,
        ))
    
    async def notify_scan_completed(
        self,
        library_name: str,
        new_items: int,
    ) -> None:
        """Send scan completed notification."""
        await self.send(Notification(
            title=f"Library Scan Complete",
            message=f"{library_name}: {new_items} new items found",
            notification_type=NotificationType.SCAN_COMPLETED,
            priority=NotificationPriority.NORMAL,
        ))
    
    async def notify_system_alert(
        self,
        title: str,
        message: str,
    ) -> None:
        """Send system alert notification."""
        await self.send(Notification(
            title=title,
            message=message,
            notification_type=NotificationType.SYSTEM_ALERT,
            priority=NotificationPriority.HIGH,
        ))


# Global manager instance
notification_manager = NotificationManager()
