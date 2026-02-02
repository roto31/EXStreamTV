"""
Plugin System Architecture

Provides:
- Plugin discovery and loading
- Plugin lifecycle management
- Plugin API for custom sources
- Event hooks
"""

import asyncio
import importlib
import importlib.util
import inspect
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
import logging

logger = logging.getLogger(__name__)


class PluginType(str, Enum):
    """Types of plugins."""
    SOURCE = "source"          # Channel/media source
    PROVIDER = "provider"      # Metadata provider
    NOTIFICATION = "notification"  # Notification service
    PROCESSOR = "processor"    # Stream processor
    UI = "ui"                  # UI extension


class PluginState(str, Enum):
    """Plugin states."""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class HookType(str, Enum):
    """Types of plugin hooks."""
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    STREAM_START = "stream_start"
    STREAM_STOP = "stream_stop"
    CHANNEL_ADDED = "channel_added"
    SCAN_COMPLETE = "scan_complete"
    ERROR = "error"


@dataclass
class PluginInfo:
    """Plugin metadata."""
    
    id: str
    name: str
    version: str
    author: str
    description: str
    plugin_type: PluginType
    
    # Optional metadata
    homepage: Optional[str] = None
    license: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    
    # Requirements
    min_app_version: Optional[str] = None
    python_packages: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "type": self.plugin_type.value,
            "homepage": self.homepage,
        }


@dataclass
class PluginContext:
    """Context passed to plugins."""
    
    app_version: str
    data_dir: Path
    config_dir: Path
    
    # Services
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("plugin"))
    
    def get_data_file(self, filename: str) -> Path:
        """Get path to a plugin data file."""
        return self.data_dir / filename
    
    def get_config_file(self, filename: str) -> Path:
        """Get path to a plugin config file."""
        return self.config_dir / filename


class Plugin(ABC):
    """
    Base class for all plugins.
    
    Plugins must:
    - Implement get_info() to return metadata
    - Implement async setup() and teardown() for lifecycle
    """
    
    def __init__(self, context: PluginContext):
        self.context = context
        self._state = PluginState.LOADED
        self._hooks: Dict[HookType, List[Callable]] = {}
    
    @abstractmethod
    def get_info(self) -> PluginInfo:
        """Return plugin metadata."""
        pass
    
    @abstractmethod
    async def setup(self) -> bool:
        """
        Setup the plugin.
        
        Called when the plugin is enabled.
        Return True on success.
        """
        pass
    
    @abstractmethod
    async def teardown(self) -> None:
        """
        Teardown the plugin.
        
        Called when the plugin is disabled or app shuts down.
        """
        pass
    
    def register_hook(
        self,
        hook_type: HookType,
        callback: Callable,
    ) -> None:
        """Register a hook callback."""
        if hook_type not in self._hooks:
            self._hooks[hook_type] = []
        self._hooks[hook_type].append(callback)
    
    def get_hooks(self, hook_type: HookType) -> List[Callable]:
        """Get registered hooks for a type."""
        return self._hooks.get(hook_type, [])
    
    @property
    def state(self) -> PluginState:
        return self._state
    
    @state.setter
    def state(self, value: PluginState) -> None:
        self._state = value


class SourcePlugin(Plugin):
    """
    Base class for source plugins.
    
    Source plugins provide channels or media items.
    """
    
    @abstractmethod
    async def get_channels(self) -> List[Dict[str, Any]]:
        """Get available channels from this source."""
        pass
    
    @abstractmethod
    async def get_stream_url(self, channel_id: str) -> Optional[str]:
        """Get stream URL for a channel."""
        pass
    
    async def refresh(self) -> bool:
        """Refresh source data."""
        return True


class ProviderPlugin(Plugin):
    """
    Base class for metadata provider plugins.
    
    Provider plugins supply metadata for media items.
    """
    
    @abstractmethod
    async def search(
        self,
        query: str,
        media_type: str,
    ) -> List[Dict[str, Any]]:
        """Search for media by query."""
        pass
    
    @abstractmethod
    async def get_metadata(
        self,
        item_id: str,
        media_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Get metadata for an item."""
        pass


class NotificationPlugin(Plugin):
    """
    Base class for notification plugins.
    
    Notification plugins send alerts via custom services.
    """
    
    @abstractmethod
    async def send(
        self,
        title: str,
        message: str,
        priority: str = "normal",
    ) -> bool:
        """Send a notification."""
        pass
    
    @abstractmethod
    async def test(self) -> tuple[bool, str]:
        """Test the notification service."""
        pass


@dataclass
class LoadedPlugin:
    """A loaded plugin with its state."""
    
    info: PluginInfo
    instance: Plugin
    state: PluginState
    path: Path
    load_time: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


class PluginManager:
    """
    Central plugin manager.
    
    Features:
    - Plugin discovery from directory
    - Plugin loading and lifecycle
    - Hook dispatching
    - Plugin isolation
    """
    
    def __init__(
        self,
        plugin_dir: Path,
        data_dir: Path,
        app_version: str = "1.0.0",
    ):
        self.plugin_dir = plugin_dir
        self.data_dir = data_dir
        self.app_version = app_version
        
        self._plugins: Dict[str, LoadedPlugin] = {}
        self._hooks: Dict[HookType, List[tuple[str, Callable]]] = {}
        
        # Ensure directories exist
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def discover_plugins(self) -> List[PluginInfo]:
        """
        Discover plugins in the plugin directory.
        
        Looks for Python packages with a 'plugin.py' containing
        a Plugin subclass.
        """
        discovered = []
        
        for item in self.plugin_dir.iterdir():
            if item.is_dir() and (item / "plugin.py").exists():
                try:
                    info = self._load_plugin_info(item)
                    if info:
                        discovered.append(info)
                except Exception as e:
                    logger.error(f"Failed to discover plugin at {item}: {e}")
        
        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered
    
    async def load_plugin(self, plugin_id: str) -> bool:
        """Load a discovered plugin."""
        plugin_path = self.plugin_dir / plugin_id
        
        if not plugin_path.exists():
            logger.error(f"Plugin not found: {plugin_id}")
            return False
        
        try:
            # Create plugin context
            context = PluginContext(
                app_version=self.app_version,
                data_dir=self.data_dir / plugin_id,
                config_dir=plugin_path / "config",
                logger=logging.getLogger(f"plugin.{plugin_id}"),
            )
            context.data_dir.mkdir(parents=True, exist_ok=True)
            
            # Load plugin module
            module = self._load_module(plugin_path / "plugin.py")
            
            # Find plugin class
            plugin_class = self._find_plugin_class(module)
            if not plugin_class:
                logger.error(f"No Plugin class found in {plugin_id}")
                return False
            
            # Instantiate plugin
            instance = plugin_class(context)
            info = instance.get_info()
            
            loaded = LoadedPlugin(
                info=info,
                instance=instance,
                state=PluginState.LOADED,
                path=plugin_path,
            )
            
            self._plugins[plugin_id] = loaded
            logger.info(f"Loaded plugin: {info.name} v{info.version}")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}: {e}")
            return False
    
    async def enable_plugin(self, plugin_id: str) -> bool:
        """Enable a loaded plugin."""
        loaded = self._plugins.get(plugin_id)
        if not loaded:
            return False
        
        try:
            success = await loaded.instance.setup()
            if success:
                loaded.state = PluginState.ENABLED
                loaded.instance.state = PluginState.ENABLED
                
                # Register hooks
                for hook_type in HookType:
                    for callback in loaded.instance.get_hooks(hook_type):
                        if hook_type not in self._hooks:
                            self._hooks[hook_type] = []
                        self._hooks[hook_type].append((plugin_id, callback))
                
                logger.info(f"Enabled plugin: {loaded.info.name}")
                return True
            else:
                loaded.state = PluginState.ERROR
                loaded.error = "Setup returned False"
                return False
        
        except Exception as e:
            loaded.state = PluginState.ERROR
            loaded.error = str(e)
            logger.error(f"Failed to enable plugin {plugin_id}: {e}")
            return False
    
    async def disable_plugin(self, plugin_id: str) -> bool:
        """Disable an enabled plugin."""
        loaded = self._plugins.get(plugin_id)
        if not loaded:
            return False
        
        try:
            await loaded.instance.teardown()
            loaded.state = PluginState.DISABLED
            loaded.instance.state = PluginState.DISABLED
            
            # Remove hooks
            for hook_type in self._hooks:
                self._hooks[hook_type] = [
                    (pid, cb) for pid, cb in self._hooks[hook_type]
                    if pid != plugin_id
                ]
            
            logger.info(f"Disabled plugin: {loaded.info.name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to disable plugin {plugin_id}: {e}")
            return False
    
    async def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin completely."""
        if plugin_id not in self._plugins:
            return False
        
        loaded = self._plugins[plugin_id]
        
        # Disable first if enabled
        if loaded.state == PluginState.ENABLED:
            await self.disable_plugin(plugin_id)
        
        del self._plugins[plugin_id]
        logger.info(f"Unloaded plugin: {plugin_id}")
        return True
    
    async def dispatch_hook(
        self,
        hook_type: HookType,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Dispatch a hook to all registered plugins.
        
        Returns dict mapping plugin ID to result.
        """
        results = {}
        
        for plugin_id, callback in self._hooks.get(hook_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    result = await callback(*args, **kwargs)
                else:
                    result = callback(*args, **kwargs)
                results[plugin_id] = result
            except Exception as e:
                logger.error(f"Hook error in {plugin_id}: {e}")
                results[plugin_id] = {"error": str(e)}
        
        return results
    
    def get_plugin(self, plugin_id: str) -> Optional[LoadedPlugin]:
        """Get a loaded plugin."""
        return self._plugins.get(plugin_id)
    
    def get_plugins(
        self,
        plugin_type: Optional[PluginType] = None,
        state: Optional[PluginState] = None,
    ) -> List[LoadedPlugin]:
        """Get plugins, optionally filtered."""
        plugins = list(self._plugins.values())
        
        if plugin_type:
            plugins = [p for p in plugins if p.info.plugin_type == plugin_type]
        
        if state:
            plugins = [p for p in plugins if p.state == state]
        
        return plugins
    
    def get_source_plugins(self) -> List[SourcePlugin]:
        """Get enabled source plugins."""
        return [
            p.instance for p in self._plugins.values()
            if isinstance(p.instance, SourcePlugin)
            and p.state == PluginState.ENABLED
        ]
    
    def get_provider_plugins(self) -> List[ProviderPlugin]:
        """Get enabled provider plugins."""
        return [
            p.instance for p in self._plugins.values()
            if isinstance(p.instance, ProviderPlugin)
            and p.state == PluginState.ENABLED
        ]
    
    async def shutdown(self) -> None:
        """Shutdown all plugins."""
        for plugin_id in list(self._plugins.keys()):
            await self.disable_plugin(plugin_id)
        
        logger.info("All plugins shut down")
    
    def _load_plugin_info(self, plugin_path: Path) -> Optional[PluginInfo]:
        """Load plugin info without fully loading the plugin."""
        manifest_path = plugin_path / "manifest.json"
        
        if manifest_path.exists():
            import json
            with open(manifest_path) as f:
                data = json.load(f)
            
            return PluginInfo(
                id=plugin_path.name,
                name=data.get("name", plugin_path.name),
                version=data.get("version", "0.0.0"),
                author=data.get("author", "Unknown"),
                description=data.get("description", ""),
                plugin_type=PluginType(data.get("type", "source")),
                homepage=data.get("homepage"),
                license=data.get("license"),
                dependencies=data.get("dependencies", []),
                python_packages=data.get("python_packages", []),
            )
        
        return None
    
    def _load_module(self, module_path: Path):
        """Load a Python module from path."""
        spec = importlib.util.spec_from_file_location(
            module_path.stem,
            module_path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    
    def _find_plugin_class(self, module) -> Optional[Type[Plugin]]:
        """Find Plugin subclass in module."""
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, Plugin) and 
                obj is not Plugin and
                obj not in (SourcePlugin, ProviderPlugin, NotificationPlugin)):
                return obj
        return None


# Global plugin manager
plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> Optional[PluginManager]:
    """Get the global plugin manager."""
    return plugin_manager


async def setup_plugins(
    plugin_dir: Path,
    data_dir: Path,
    app_version: str = "1.0.0",
) -> PluginManager:
    """Setup the plugin system."""
    global plugin_manager
    
    plugin_manager = PluginManager(
        plugin_dir=plugin_dir,
        data_dir=data_dir,
        app_version=app_version,
    )
    
    # Discover and auto-load plugins
    await plugin_manager.discover_plugins()
    
    return plugin_manager


async def shutdown_plugins() -> None:
    """Shutdown the plugin system."""
    global plugin_manager
    
    if plugin_manager:
        await plugin_manager.shutdown()
        plugin_manager = None
