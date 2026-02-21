"""
EXStreamTV Main Application

FastAPI application entry point combining StreamTV and ErsatzTV features.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from exstreamtv import __version__
from exstreamtv.config import get_config, load_config
from exstreamtv.database import init_db

# Logger
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown tasks:
    - Load configuration
    - Initialize database
    - Start channel manager
    - Initialize SSDP discovery
    """
    # Startup
    logger.info(f"Starting EXStreamTV v{__version__}")
    
    # Load configuration
    config = load_config()
    logger.info(f"Configuration loaded, server port: {config.server.port}")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize cache manager
    try:
        from exstreamtv.cache import cache_manager
        await cache_manager.initialize()
        logger.info("Cache manager initialized")
    except Exception as e:
        logger.warning(f"Cache manager initialization failed (non-critical): {e}")
    
    # Initialize task queue
    try:
        from exstreamtv.tasks import task_queue
        await task_queue.start()
        logger.info("Task queue started")
    except Exception as e:
        logger.warning(f"Task queue initialization failed (non-critical): {e}")
    
    # Register background tasks
    try:
        from exstreamtv.tasks.scheduler import scheduler
        from exstreamtv.tasks.playout_tasks import rebuild_playouts_task
        from exstreamtv.tasks.url_refresh_task import refresh_urls_task
        from exstreamtv.tasks.health_tasks import channel_health_task
        
        # Playout rebuild every 5 minutes
        scheduler.add_task("playout_rebuild", rebuild_playouts_task, 300, run_immediately=False)
        
        # URL refresh every 15 minutes
        scheduler.add_task("url_refresh", refresh_urls_task, 900, run_immediately=False)
        
        # Channel health check every 30 seconds
        scheduler.add_task("channel_health", channel_health_task, 30, run_immediately=False)
        
        await scheduler.start()
        logger.info("Background task scheduler started with 3 tasks")
    except Exception as e:
        logger.warning(f"Background task scheduler initialization failed: {e}")
    
    # Initialize FFmpeg process pool (legacy)
    try:
        from exstreamtv.ffmpeg.process_pool import get_process_pool
        await get_process_pool()
        logger.info("FFmpeg process pool initialized")
    except Exception as e:
        logger.warning(f"FFmpeg process pool initialization failed (non-critical): {e}")

    # Initialize ProcessPoolManager (remediation: sole FFmpeg spawn gatekeeper)
    process_pool_manager = None
    try:
        from exstreamtv.streaming.process_pool_manager import get_process_pool_manager
        process_pool_manager = get_process_pool_manager()
        await process_pool_manager.start()
        app.state.process_pool_manager = process_pool_manager
        logger.info("ProcessPoolManager initialized")
    except Exception as e:
        logger.warning(f"ProcessPoolManager initialization failed (non-critical): {e}")

    # Initialize channel manager
    try:
        from exstreamtv.streaming.channel_manager import ChannelManager
        from exstreamtv.database import get_sync_session_factory
        db_session_factory = get_sync_session_factory()
        app.state.channel_manager = ChannelManager(
            db_session_factory=db_session_factory,
            process_pool_manager=process_pool_manager,
        )
        await app.state.channel_manager.start()
        logger.info("Channel manager started")
        # #region agent log
        try:
            import json as _j
            with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as _f:
                _f.write(_j.dumps({"hypothesisId":"H2","location":"main.py:lifespan:channel_manager","message":"channel_manager_set","data":{},"timestamp":__import__("datetime").datetime.utcnow().isoformat(),"sessionId":"debug-session"}) + "\n")
        except Exception:
            pass
        # #endregion
        
        # Register channel manager with health tasks for restart capability
        try:
            from exstreamtv.tasks.health_tasks import set_channel_manager
            set_channel_manager(app.state.channel_manager)
        except Exception as e:
            logger.warning(f"Failed to register channel manager with health tasks: {e}")
        
        # Pre-warm channels for faster cold-start response
        try:
            prewarm_results = await app.state.channel_manager.prewarm_channels()
            if prewarm_results:
                success = sum(1 for v in prewarm_results.values() if v)
                logger.info(f"Channel pre-warming complete: {success}/{len(prewarm_results)} channels ready")
        except Exception as e:
            logger.warning(f"Channel pre-warming failed (non-critical): {e}")
            
    except Exception as e:
        logger.warning(f"Channel manager initialization failed: {e}")
        # #region agent log
        try:
            import json as _j
            with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as _f:
                _f.write(_j.dumps({"hypothesisId":"H2","location":"main.py:lifespan:channel_manager_except","message":"channel_manager_init_failed","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":__import__("datetime").datetime.utcnow().isoformat(),"sessionId":"debug-session"}) + "\n")
        except Exception:
            pass
        # #endregion
    
    # Start SSDP discovery for HDHomeRun emulation
    if config.hdhomerun.enabled:
        try:
            # Import ssdp_server directly to avoid triggering api.py imports
            from exstreamtv.hdhomerun.ssdp_server import SSDPServer
            app.state.ssdp = SSDPServer()
            app.state.ssdp.start()  # Note: start() is not async in SSDPServer
            logger.info("SSDP server started for HDHomeRun emulation")
        except Exception as e:
            logger.warning(f"SSDP server initialization failed: {e}")
    
    # Start log lifecycle management
    try:
        from exstreamtv.utils.log_lifecycle_manager import get_log_lifecycle_manager
        config = get_config()
        if config.logging.lifecycle.enabled:
            lifecycle_manager = get_log_lifecycle_manager()
            await lifecycle_manager.start()
            app.state.lifecycle_manager = lifecycle_manager
            logger.info("Log lifecycle management started")
    except Exception as e:
        logger.warning(f"Log lifecycle management initialization failed (non-critical): {e}")
    
    # Initialize session manager (Tunarr-style)
    try:
        from exstreamtv.streaming.session_manager import init_session_manager
        config = get_config()
        session_manager = await init_session_manager(
            max_sessions_per_channel=config.session_manager.max_sessions_per_channel,
            idle_timeout=config.session_manager.idle_timeout_seconds,
        )
        app.state.session_manager = session_manager
        logger.info("Session manager started")
    except Exception as e:
        logger.warning(f"Session manager initialization failed (non-critical): {e}")
    
    # Initialize database backup manager
    try:
        from exstreamtv.database.backup import init_backup_manager, BackupConfig
        config = get_config()
        if config.database_backup.enabled:
            backup_config = BackupConfig(
                enabled=config.database_backup.enabled,
                backup_directory=config.database_backup.backup_directory,
                interval_hours=config.database_backup.interval_hours,
                keep_count=config.database_backup.keep_count,
                keep_days=config.database_backup.keep_days,
                compress=config.database_backup.compress,
            )
            backup_manager = await init_backup_manager(backup_config, start=True)
            app.state.backup_manager = backup_manager
            logger.info("Database backup manager started")
    except Exception as e:
        logger.warning(f"Database backup manager initialization failed (non-critical): {e}")
    
    # Initialize AI self-healing components
    try:
        config = get_config()
        if config.ai_auto_heal.enabled:
            # Initialize unified log collector
            from exstreamtv.ai_agent.unified_log_collector import init_log_collector
            log_collector = await init_log_collector(
                buffer_minutes=config.ai_auto_heal.log_buffer_minutes,
            )
            app.state.log_collector = log_collector
            logger.info("Unified log collector started")
            
            # Initialize FFmpeg AI monitor
            if config.ai_auto_heal.ffmpeg_monitor_enabled:
                from exstreamtv.ai_agent.ffmpeg_monitor import get_ffmpeg_monitor
                ffmpeg_monitor = get_ffmpeg_monitor()
                app.state.ffmpeg_monitor = ffmpeg_monitor
                logger.info("FFmpeg AI monitor initialized")
            
            # Initialize pattern detector
            if config.ai_auto_heal.pattern_detection_enabled:
                from exstreamtv.ai_agent.pattern_detector import get_pattern_detector
                pattern_detector = get_pattern_detector()
                app.state.pattern_detector = pattern_detector
                logger.info("Pattern detector initialized")
            
            # Initialize auto resolver
            if config.ai_auto_heal.auto_resolve_enabled:
                from exstreamtv.ai_agent.auto_resolver import get_auto_resolver, ResolverConfig
                resolver_config = ResolverConfig(
                    enabled=True,
                    auto_resolve_enabled=True,
                    max_auto_fixes_per_hour=config.ai_auto_heal.max_auto_fixes_per_hour,
                    use_fallback_stream=config.ai_auto_heal.use_error_screen_fallback,
                    hot_swap_enabled=config.ai_auto_heal.hot_swap_enabled,
                    learning_enabled=config.ai_auto_heal.learning_enabled,
                )
                auto_resolver = get_auto_resolver(resolver_config)
                
                # Connect to channel manager for restart operations
                if hasattr(app.state, 'channel_manager'):
                    auto_resolver.set_channel_manager(app.state.channel_manager)
                if hasattr(app.state, 'session_manager'):
                    auto_resolver.set_session_manager(app.state.session_manager)
                
                app.state.auto_resolver = auto_resolver
                logger.info("Auto resolver initialized")
            
            logger.info("AI self-healing system initialized")
    except Exception as e:
        logger.warning(f"AI self-healing initialization failed (non-critical): {e}")
    
    logger.info("EXStreamTV started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down EXStreamTV")
    
    # Stop AI components
    if hasattr(app.state, 'log_collector'):
        try:
            await app.state.log_collector.stop()
            logger.info("Log collector stopped")
        except Exception as e:
            logger.warning(f"Error stopping log collector: {e}")
    
    # Stop backup manager
    if hasattr(app.state, 'backup_manager'):
        try:
            await app.state.backup_manager.stop()
            logger.info("Backup manager stopped")
        except Exception as e:
            logger.warning(f"Error stopping backup manager: {e}")
    
    # Stop session manager
    if hasattr(app.state, 'session_manager'):
        try:
            await app.state.session_manager.stop()
            logger.info("Session manager stopped")
        except Exception as e:
            logger.warning(f"Error stopping session manager: {e}")
    
    # Stop log lifecycle management
    if hasattr(app.state, 'lifecycle_manager'):
        try:
            await app.state.lifecycle_manager.stop()
            logger.info("Log lifecycle management stopped")
        except Exception as e:
            logger.warning(f"Error stopping lifecycle manager: {e}")
    
    # Stop SSDP server
    if hasattr(app.state, 'ssdp'):
        try:
            app.state.ssdp.stop()  # Note: stop() is not async in SSDPServer
            logger.info("SSDP server stopped")
        except Exception as e:
            logger.warning(f"Error stopping SSDP: {e}")
    
    # Stop channel manager
    if hasattr(app.state, 'channel_manager'):
        try:
            await app.state.channel_manager.stop()
            logger.info("Channel manager stopped")
        except Exception as e:
            logger.warning(f"Error stopping channel manager: {e}")
    
    # Stop ProcessPoolManager (remediation)
    if hasattr(app.state, "process_pool_manager") and app.state.process_pool_manager:
        try:
            from exstreamtv.streaming.process_pool_manager import shutdown_process_pool_manager
            await shutdown_process_pool_manager()
            logger.info("ProcessPoolManager stopped")
        except Exception as e:
            logger.warning(f"Error stopping ProcessPoolManager: {e}")

    # Stop FFmpeg process pool
    try:
        from exstreamtv.ffmpeg.process_pool import shutdown_process_pool
        await shutdown_process_pool()
        logger.info("FFmpeg process pool stopped")
    except Exception as e:
        logger.warning(f"Error stopping FFmpeg pool: {e}")
    
    # Stop task queue
    try:
        from exstreamtv.tasks import task_queue
        await task_queue.stop()
        logger.info("Task queue stopped")
    except Exception as e:
        logger.warning(f"Error stopping task queue: {e}")
    
    # Shutdown cache
    try:
        from exstreamtv.cache import cache_manager
        await cache_manager.shutdown()
        logger.info("Cache manager stopped")
    except Exception as e:
        logger.warning(f"Error stopping cache: {e}")
    
    # Close database connections
    try:
        from exstreamtv.database.connection import close_db
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning(f"Error closing database: {e}")
    
    logger.info("EXStreamTV shutdown complete")

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="EXStreamTV",
        description="Unified IPTV streaming platform combining StreamTV and ErsatzTV",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    
    # Get paths
    base_path = Path(__file__).parent
    templates_path = base_path / "templates"
    static_path = base_path / "static"
    
    # Mount static files
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")
    
    # Mount documentation screenshots
    docs_screenshots_path = base_path.parent / "docs" / "guides" / "screenshots"
    if docs_screenshots_path.exists():
        app.mount("/docs/screenshots", StaticFiles(directory=docs_screenshots_path), name="docs_screenshots")
        logger.info(f"Documentation screenshots mounted at /docs/screenshots")
    
    # Setup templates
    templates = Jinja2Templates(directory=templates_path) if templates_path.exists() else None
    app.state.templates = templates

    # Register API routers
    from exstreamtv.api import api_router, iptv_router
    app.include_router(api_router)
    
    # Mount IPTV router at root level (not under /api) for StreamTV compatibility
    # This makes URLs like /iptv/xmltv.xml instead of /api/iptv/xmltv.xml
    if iptv_router:
        app.include_router(iptv_router, tags=["IPTV"])
        logger.info("IPTV router mounted at root level for StreamTV compatibility")
    
    # Try to include performance and integrations routers
    try:
        from exstreamtv.api import performance
        app.include_router(performance.router, prefix="/api", tags=["Performance"])
    except ImportError as e:
        logger.warning(f"Performance router not available: {e}")
    
    try:
        from exstreamtv.api import integrations
        app.include_router(integrations.router, prefix="/api", tags=["Integrations"])
    except ImportError as e:
        logger.warning(f"Integrations router not available: {e}")
    
    # AI Channel Creator router
    try:
        from exstreamtv.api import ai_channel
        app.include_router(ai_channel.router, prefix="/api", tags=["AI Channel Creator"])
        logger.info("AI Channel Creator router registered")
    except ImportError as e:
        logger.warning(f"AI Channel Creator router not available: {e}")
    
    # Documentation router (markdown-based docs)
    try:
        from exstreamtv.api import docs as docs_api
        app.include_router(docs_api.router, tags=["Documentation"])
        logger.info("Documentation router registered")
    except ImportError as e:
        logger.warning(f"Documentation router not available: {e}")
    
    # HDHomeRun router for Plex/Emby/Jellyfin integration
    try:
        from exstreamtv.hdhomerun import api as hdhomerun_api
        app.include_router(hdhomerun_api.hdhomerun_router, tags=["HDHomeRun"])
        logger.info("HDHomeRun router registered")
        
        # Add root-level HDHomeRun endpoints for clients that expect them at the root
        # Some media servers (Plex, Emby) expect discover.json at the root path
        from fastapi.responses import RedirectResponse
        
        @app.get("/discover.json", include_in_schema=False)
        async def root_discover():
            """Redirect to /hdhomerun/discover.json for clients expecting root-level access"""
            return RedirectResponse(url="/hdhomerun/discover.json", status_code=307)
        
        @app.get("/lineup_status.json", include_in_schema=False)
        async def root_lineup_status():
            """Redirect to /hdhomerun/lineup_status.json for clients expecting root-level access"""
            return RedirectResponse(url="/hdhomerun/lineup_status.json", status_code=307)
        
        @app.get("/lineup.json", include_in_schema=False)
        async def root_lineup():
            """Redirect to /hdhomerun/lineup.json for clients expecting root-level access"""
            return RedirectResponse(url="/hdhomerun/lineup.json", status_code=307)
        
        logger.info("Root-level HDHomeRun redirects registered")
    except ImportError as e:
        logger.warning(f"HDHomeRun router not available: {e}")
    
    # Migration router for ErsatzTV/StreamTV imports
    try:
        from exstreamtv.api import migration_api
        app.include_router(migration_api.router, prefix="/api/migration", tags=["Migration"])
        logger.info("Migration router registered")
    except ImportError as e:
        logger.warning(f"Migration router not available: {e}")
    
    # AI Settings router
    try:
        from exstreamtv.api import ai_settings
        app.include_router(ai_settings.router, prefix="/api", tags=["AI Settings"])
        logger.info("AI Settings router registered")
    except ImportError as e:
        logger.warning(f"AI Settings router not available: {e}")

    # Prometheus metrics exporter (GET /metrics)
    try:
        from exstreamtv.monitoring.prometheus_exporter import create_prometheus_router
        from exstreamtv.streaming.process_pool_manager import get_process_pool_manager
        from exstreamtv.monitoring.metrics import get_metrics_collector

        def get_db_metrics() -> dict:
            try:
                from exstreamtv.database import get_connection_manager
                cm = get_connection_manager()
                if cm and hasattr(cm, "get_metrics"):
                    m = cm.get_metrics()
                    return {
                        "checked_out": getattr(m, "checked_out", 0),
                        "size": getattr(m, "pool_size", 0),
                    }
            except Exception:
                pass
            return {}

        prom_router = create_prometheus_router(
            get_process_pool_metrics=get_process_pool_manager,
            get_metrics_collector=get_metrics_collector,
            get_db_metrics=get_db_metrics,
        )
        app.include_router(prom_router, tags=["Monitoring"])
        logger.info("Prometheus /metrics endpoint registered")
    except ImportError as e:
        logger.warning(f"Prometheus exporter not available: {e}")
    
    # Plex image proxy - forwards /library/metadata/*/thumb/* to Plex server
    @app.get("/library/metadata/{rating_key}/thumb/{thumb_id}", include_in_schema=False)
    async def plex_thumb_proxy(rating_key: str, thumb_id: str):
        """Proxy Plex thumbnail requests to the Plex server."""
        import httpx
        from fastapi.responses import Response
        from exstreamtv.config import get_config
        
        config = get_config()
        plex_url = getattr(config.plex, "url", None) or getattr(config.plex, "base_url", None)
        plex_token = getattr(config.plex, "token", None)
        
        if not plex_url or not plex_token:
            return Response(content=b"", status_code=404)
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{plex_url.rstrip('/')}/library/metadata/{rating_key}/thumb/{thumb_id}",
                    headers={"X-Plex-Token": plex_token},
                )
                
                if response.status_code == 200:
                    return Response(
                        content=response.content,
                        media_type=response.headers.get("content-type", "image/jpeg"),
                        headers={"Cache-Control": "public, max-age=86400"},  # Cache for 24 hours
                    )
                else:
                    return Response(content=b"", status_code=404)
        except Exception:
            return Response(content=b"", status_code=404)
    
    logger.info("Plex thumbnail proxy registered at /library/metadata/*/thumb/*")

    # Root redirect
    @app.get("/", response_model=None)
    async def root(request: Request):
        """Root endpoint - redirect to dashboard."""
        return RedirectResponse(url="/dashboard")
    
    # Dashboard
    @app.get("/dashboard", response_model=None)
    async def dashboard_page(request: Request):
        """Dashboard page."""
        if templates:
            return templates.TemplateResponse(
                "dashboard.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Program Guide
    @app.get("/guide", response_model=None)
    async def guide_page(request: Request):
        """Program guide page."""
        if templates:
            return templates.TemplateResponse(
                "guide.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Media Browser
    @app.get("/browse", response_model=None)
    async def media_browser_page(request: Request):
        """Media browser page."""
        if templates:
            return templates.TemplateResponse(
                "media_browser.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Schedule Builder
    @app.get("/schedule-builder", response_model=None)
    async def schedule_builder_page(request: Request):
        """Schedule builder page."""
        if templates:
            return templates.TemplateResponse(
                "schedule_builder.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # System Monitor
    @app.get("/monitor", response_model=None)
    async def system_monitor_page(request: Request):
        """System monitor page."""
        if templates:
            return templates.TemplateResponse(
                "system_monitor.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Channel Editor
    @app.get("/channel-editor", response_model=None)
    async def channel_editor_page(request: Request):
        """Channel editor page."""
        if templates:
            return templates.TemplateResponse(
                "channel_editor.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Channels page
    @app.get("/channels", response_model=None)
    async def channels_page(request: Request):
        """Channels management page."""
        if templates:
            return templates.TemplateResponse(
                "channels.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Import page
    @app.get("/import", response_model=None)
    async def import_page(request: Request):
        """Import page."""
        if templates:
            return templates.TemplateResponse(
                "import.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Media page
    @app.get("/media", response_model=None)
    async def media_page(request: Request):
        """Media items page."""
        if templates:
            return templates.TemplateResponse(
                "media.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Playlists page
    @app.get("/playlists", response_model=None)
    async def playlists_page(request: Request):
        """Playlists page."""
        if templates:
            return templates.TemplateResponse(
                "playlists.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Collections page
    @app.get("/collections", response_model=None)
    async def collections_page(request: Request):
        """Collections page."""
        if templates:
            return templates.TemplateResponse(
                "collections.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Playouts page
    @app.get("/playouts", response_model=None)
    async def playouts_page(request: Request):
        """Playouts page."""
        if templates:
            return templates.TemplateResponse(
                "playouts.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Schedules page
    @app.get("/schedules", response_model=None)
    async def schedules_page(request: Request):
        """Schedules page."""
        if templates:
            return templates.TemplateResponse(
                "schedules.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/blocks", response_model=None)
    async def blocks_page(request: Request):
        """Blocks page for time-based programming."""
        if templates:
            return templates.TemplateResponse(
                "blocks.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/templates", response_model=None)
    async def schedule_templates_page(request: Request):
        """Schedule templates page."""
        if templates:
            return templates.TemplateResponse(
                "schedule_templates.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/filler-presets", response_model=None)
    async def filler_presets_page(request: Request):
        """Filler presets page."""
        if templates:
            return templates.TemplateResponse(
                "filler_presets.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/deco", response_model=None)
    async def deco_page(request: Request):
        """Deco page for bumpers, station IDs, and promos."""
        if templates:
            return templates.TemplateResponse(
                "deco.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Settings pages
    @app.get("/settings", response_model=None)
    async def settings_main_page():
        """Redirect to FFmpeg settings as default."""
        return RedirectResponse(url="/settings/ffmpeg")
    
    @app.get("/settings/ffmpeg", response_model=None)
    async def settings_ffmpeg_page(request: Request):
        """FFmpeg settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_ffmpeg.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/settings/hdhr", response_model=None)
    async def settings_hdhr_page(request: Request):
        """HDHomeRun settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_hdhr.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/settings/hdhomerun", response_model=None)
    async def settings_hdhomerun_page(request: Request):
        """HDHomeRun settings page (alias)."""
        if templates:
            return templates.TemplateResponse(
                "settings_hdhr.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/settings/playout", response_model=None)
    async def settings_playout_page(request: Request):
        """Playout settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_playout.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")

    @app.get("/settings/streaming", response_model=None)
    async def settings_streaming_page(request: Request):
        """Streaming and stream throttler settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_streaming.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")

    @app.get("/settings/plex", response_model=None)
    async def settings_plex_page(request: Request):
        """Plex settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_plex.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Health check alias - redirects to HTML page
    @app.get("/health-check", response_model=None)
    async def health_check_redirect():
        """Redirect to health check page."""
        return RedirectResponse(url="/health-page")
    
    # Player page
    @app.get("/player", response_model=None)
    async def player_page(request: Request):
        """Player page."""
        if templates:
            return templates.TemplateResponse(
                "player.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Health check JSON endpoint
    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": __version__,
            "app": "EXStreamTV",
        }
    
    # Health check HTML page
    @app.get("/health-page", response_model=None)
    async def health_check_page(request: Request):
        """Health check page."""
        if templates:
            return templates.TemplateResponse(
                "health_check.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/health")
    
    # Version info
    @app.get("/version")
    async def version_info() -> dict:
        """Version information endpoint."""
        return {
            "version": __version__,
            "app": "EXStreamTV",
            "description": "Unified IPTV streaming platform",
        }
    
    # Logs page
    @app.get("/logs", response_model=None)
    async def logs_page(request: Request):
        """Streaming logs page."""
        if templates:
            return templates.TemplateResponse(
                "logs.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Plex logs page
    @app.get("/plex-logs", response_model=None)
    async def plex_logs_page(request: Request):
        """Plex server logs page."""
        if templates:
            return templates.TemplateResponse(
                "plex_logs.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # AI Troubleshooting / Ollama page
    @app.get("/ollama", response_model=None)
    async def ollama_page(request: Request):
        """AI Troubleshooting assistant page."""
        if templates:
            return templates.TemplateResponse(
                "ollama.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/ai-troubleshooting", response_model=None)
    async def ai_troubleshooting_page(request: Request):
        """AI Troubleshooting assistant page (alias)."""
        if templates:
            return templates.TemplateResponse(
                "ollama.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # AI Settings page
    @app.get("/settings/ai", response_model=None)
    async def settings_ai_page(request: Request):
        """AI Settings page."""
        if templates:
            return templates.TemplateResponse(
                "ai_settings.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/ai-settings", response_model=None)
    async def ai_settings_page(request: Request):
        """AI Settings page (alias)."""
        if templates:
            return templates.TemplateResponse(
                "ai_settings.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Test stream page
    @app.get("/test-stream", response_model=None)
    async def test_stream_page(request: Request):
        """Test stream page."""
        if templates:
            return templates.TemplateResponse(
                "test_stream.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Documentation content
    DOC_CONTENT = {
        "main": """
        <h1>EXStreamTV Documentation</h1>
        <p>Welcome to the EXStreamTV documentation. Select a topic from the sidebar to get started.</p>
        
        <h2>Quick Links</h2>
        <ul>
            <li><a href="/docs/quick-start">Quick Start Guide</a> - Get up and running in minutes</li>
            <li><a href="/docs/installation">Installation Guide</a> - Detailed installation instructions</li>
            <li><a href="/docs/beginner-guide">Beginner Guide</a> - New to IPTV? Start here</li>
            <li><a href="/troubleshooting">Troubleshooting</a> - Common issues and solutions</li>
        </ul>
        
        <h2>Features</h2>
        <ul>
            <li>ErsatzTV-style continuous background streaming</li>
            <li>HDHomeRun emulation for Plex/Emby/Jellyfin</li>
            <li>M3U playlist support with XMLTV EPG</li>
            <li>FFmpeg transcoding with hardware acceleration</li>
            <li>Plex API integration for enhanced metadata</li>
            <li>Schedule-based playouts with collections</li>
        </ul>
        """,
        "quick-start": """
        <h1>Quick Start Guide</h1>
        <p>Get EXStreamTV up and running in just a few steps.</p>
        
        <h2>Step 1: Install Dependencies</h2>
        <pre><code>pip install -r requirements.txt</code></pre>
        
        <h2>Step 2: Configure Settings</h2>
        <p>Copy <code>config.example.yaml</code> to <code>config.yaml</code> and edit your settings.</p>
        
        <h2>Step 3: Start the Server</h2>
        <pre><code>python -m exstreamtv</code></pre>
        
        <h2>Step 4: Access the Dashboard</h2>
        <p>Open <a href="http://localhost:8411">http://localhost:8411</a> in your browser.</p>
        
        <h2>Next Steps</h2>
        <ul>
            <li><a href="/channels">Create your first channel</a></li>
            <li><a href="/import">Import channels from YAML</a></li>
            <li><a href="/import-m3u">Import M3U playlist</a></li>
        </ul>
        """,
        "troubleshooting": """
        <h1>Troubleshooting Guide</h1>
        <p>Having issues? Find solutions here.</p>
        
        <h2>Quick Diagnostics</h2>
        <p>Use these tools to diagnose common issues:</p>
        <ul>
            <li><a href="/health-check">Health Check</a> - Verify system status</li>
            <li><a href="/logs">Streaming Logs</a> - View real-time logs</li>
            <li><a href="/ollama">AI Troubleshooting</a> - Get AI-powered help</li>
        </ul>
        
        <h2>Common Issues</h2>
        
        <h3>FFmpeg Not Found</h3>
        <p>Ensure FFmpeg is installed and in your PATH:</p>
        <pre><code>ffmpeg -version</code></pre>
        
        <h3>Port Already in Use</h3>
        <p>If port 8411 is busy, change it in config.yaml or stop the other process:</p>
        <pre><code>lsof -i :8411</code></pre>
        
        <h3>Database Errors</h3>
        <p>Try resetting the database:</p>
        <pre><code>rm exstreamtv.db
python -m exstreamtv</code></pre>
        
        <h2>Getting More Help</h2>
        <ul>
            <li>Check the <a href="/logs">streaming logs</a> for errors</li>
            <li>Use the <a href="/ollama">AI assistant</a> for personalized help</li>
            <li>Visit the <a href="/api/docs">API documentation</a></li>
        </ul>
        """,
        "beginner-guide": """
        <h1>Beginner's Guide to EXStreamTV</h1>
        <p>New to IPTV streaming? This guide will help you understand the basics.</p>
        
        <h2>What is EXStreamTV?</h2>
        <p>EXStreamTV is a powerful IPTV streaming platform that allows you to create custom TV channels from your media library.</p>
        
        <h2>Key Concepts</h2>
        <ul>
            <li><strong>Channels</strong> - Virtual TV channels that stream your content</li>
            <li><strong>Schedules</strong> - Define when content plays on channels</li>
            <li><strong>Playouts</strong> - The generated playlist for each channel</li>
            <li><strong>Collections</strong> - Groups of media items</li>
        </ul>
        
        <h2>Getting Started</h2>
        <ol>
            <li><a href="/channels">Create a channel</a></li>
            <li>Add media to a collection</li>
            <li>Create a schedule for your channel</li>
            <li>Start streaming!</li>
        </ol>
        """,
        "installation": """
        <h1>Installation Guide</h1>
        <p>Detailed instructions for installing EXStreamTV.</p>
        
        <h2>Requirements</h2>
        <ul>
            <li>Python 3.9 or higher</li>
            <li>FFmpeg (for transcoding)</li>
            <li>4GB RAM minimum</li>
        </ul>
        
        <h2>Installation Steps</h2>
        <pre><code># Clone the repository
git clone https://github.com/yourusername/exstreamtv.git
cd exstreamtv

# Install dependencies
pip install -r requirements.txt

# Copy config
cp config.example.yaml config.yaml

# Start the server
python -m exstreamtv</code></pre>
        """,
        "default": """
        <h1>Documentation</h1>
        <p>This documentation section is coming soon.</p>
        <p>In the meantime, please explore the other sections or check the <a href="/api/docs">API documentation</a>.</p>
        """
    }
    
    # Documentation pages
    @app.get("/docs", response_model=None)
    async def docs_main_page(request: Request):
        """Main documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT["main"], "title": "Documentation"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/quick-start", response_model=None)
    async def docs_quick_start_page(request: Request):
        """Quick start documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT["quick-start"], "title": "Quick Start"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/beginner-guide", response_model=None)
    async def docs_beginner_guide_page(request: Request):
        """Beginner guide documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT.get("beginner-guide", DOC_CONTENT["default"]), "title": "Beginner Guide"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/installation", response_model=None)
    async def docs_installation_page(request: Request):
        """Installation guide documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT.get("installation", DOC_CONTENT["default"]), "title": "Installation Guide"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/path-independence", response_model=None)
    async def docs_path_independence_page(request: Request):
        """Path independence documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT.get("path-independence", DOC_CONTENT["default"]), "title": "Path Independence"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/gui-installer", response_model=None)
    async def docs_gui_installer_page(request: Request):
        """GUI installer documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT.get("gui-installer", DOC_CONTENT["default"]), "title": "GUI Installer"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/swiftui-installer", response_model=None)
    async def docs_swiftui_installer_page(request: Request):
        """SwiftUI installer documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT.get("swiftui-installer", DOC_CONTENT["default"]), "title": "SwiftUI Installer"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/swiftui-complete", response_model=None)
    async def docs_swiftui_complete_page(request: Request):
        """SwiftUI complete guide documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT.get("swiftui-complete", DOC_CONTENT["default"]), "title": "SwiftUI Complete Guide"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/swiftui-quick-start", response_model=None)
    async def docs_swiftui_quick_start_page(request: Request):
        """SwiftUI quick start documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT.get("swiftui-quick-start", DOC_CONTENT["default"]), "title": "SwiftUI Quick Start"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/building-swiftui", response_model=None)
    async def docs_building_swiftui_page(request: Request):
        """Building SwiftUI documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT.get("building-swiftui", DOC_CONTENT["default"]), "title": "Building SwiftUI"}
            )
        return RedirectResponse(url="/api/docs")
    
    # Troubleshooting pages
    @app.get("/troubleshooting", response_model=None)
    async def troubleshooting_page(request: Request):
        """Main troubleshooting page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT["troubleshooting"], "title": "Troubleshooting"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/troubleshooting", response_model=None)
    async def docs_troubleshooting_page(request: Request):
        """Troubleshooting documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT["troubleshooting"], "title": "Troubleshooting"}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/docs/troubleshooting-guide", response_model=None)
    async def docs_troubleshooting_guide_page(request: Request):
        """Troubleshooting guide documentation page."""
        if templates:
            return templates.TemplateResponse(
                "documentation.html",
                {"request": request, "version": __version__, "content": DOC_CONTENT.get("troubleshooting-guide", DOC_CONTENT["troubleshooting"]), "title": "Troubleshooting Guide"}
            )
        return RedirectResponse(url="/api/docs")
    
    # Libraries page
    @app.get("/libraries", response_model=None)
    async def libraries_page(request: Request):
        """Libraries page."""
        if templates:
            return templates.TemplateResponse(
                "libraries.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Import M3U page
    @app.get("/import-m3u", response_model=None)
    async def import_m3u_page(request: Request):
        """Import M3U page."""
        if templates:
            return templates.TemplateResponse(
                "import_m3u.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Migration page - Import from ErsatzTV/StreamTV
    @app.get("/migration", response_model=None)
    async def migration_page(request: Request):
        """Migration page for importing from ErsatzTV and StreamTV."""
        if templates:
            return templates.TemplateResponse(
                "migration.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Settings pages - Additional ones
    @app.get("/settings/quick-launch", response_model=None)
    async def settings_quick_launch_page(request: Request):
        """Quick launch settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_quick_launch.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/settings/quicklaunch", response_model=None)
    async def settings_quicklaunch_page(request: Request):
        """Quick launch settings page (alias)."""
        if templates:
            return templates.TemplateResponse(
                "settings_quick_launch.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/settings/security", response_model=None)
    async def settings_security_page(request: Request):
        """Security settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_security.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/settings/watermarks", response_model=None)
    async def settings_watermarks_page(request: Request):
        """Watermarks settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_watermarks.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/settings/resolutions", response_model=None)
    async def settings_resolutions_page(request: Request):
        """Resolutions settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_resolutions.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/settings/ffmpeg-profiles", response_model=None)
    async def settings_ffmpeg_profiles_page(request: Request):
        """FFmpeg profiles settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings_ffmpeg_profiles.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/settings/media-sources", response_model=None)
    async def settings_media_sources_page(request: Request):
        """Media sources settings page (Plex, Jellyfin, Emby)."""
        if templates:
            return templates.TemplateResponse(
                "settings_media_sources.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    # Auth pages
    @app.get("/auth/archive", response_model=None)
    async def auth_archive_page(request: Request):
        """Archive.org authentication page."""
        if templates:
            return templates.TemplateResponse(
                "auth_archive.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/auth/youtube", response_model=None)
    async def auth_youtube_page(request: Request):
        """YouTube authentication page."""
        if templates:
            return templates.TemplateResponse(
                "auth_youtube.html",
                {"request": request, "version": __version__}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/schedule-items", response_model=None)
    async def schedule_items_page(request: Request, schedule_id: int | None = None):
        """Schedule items page."""
        if templates:
            # Get schedule_id from query param if not provided
            if schedule_id is None:
                schedule_id = request.query_params.get("schedule_id")
                if schedule_id:
                    schedule_id = int(schedule_id)
            return templates.TemplateResponse(
                "schedule_items.html",
                {"request": request, "version": __version__, "schedule_id": schedule_id or 0}
            )
        return RedirectResponse(url="/api/docs")
    
    @app.get("/schedules/{schedule_id}/items", response_model=None)
    async def schedule_items_by_id_page(request: Request, schedule_id: int):
        """Schedule items page for a specific schedule."""
        if templates:
            return templates.TemplateResponse(
                "schedule_items.html",
                {"request": request, "version": __version__, "schedule_id": schedule_id}
            )
        return RedirectResponse(url="/api/docs")
    
    return app

# Create the app instance
app = create_app()

def main() -> None:
    """
    Main entry point for running the server.
    
    Called when running `python -m exstreamtv` or via the CLI.
    """
    import uvicorn
    from exstreamtv.utils.logging_setup import setup_logging
    
    config = load_config()
    
    # Parse max_size string (e.g., "10MB") to bytes
    max_size_str = config.logging.max_size.upper()
    if max_size_str.endswith("MB"):
        max_bytes = int(max_size_str[:-2]) * 1024 * 1024
    elif max_size_str.endswith("KB"):
        max_bytes = int(max_size_str[:-2]) * 1024
    elif max_size_str.endswith("GB"):
        max_bytes = int(max_size_str[:-2]) * 1024 * 1024 * 1024
    else:
        max_bytes = 10 * 1024 * 1024  # Default 10MB
    
    # Configure logging using setup_logging
    setup_logging(
        log_level=config.logging.level,
        log_file_name=config.logging.file,
        log_to_console=True,
        log_to_file=True,
        max_bytes=max_bytes,
        backup_count=config.logging.backup_count,
        log_format=config.logging.format,
    )
    
    logger.info(f"Starting EXStreamTV v{__version__}")
    
    uvicorn.run(
        "exstreamtv.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug,
        log_level=config.server.log_level.lower(),
    )

if __name__ == "__main__":
    main()
