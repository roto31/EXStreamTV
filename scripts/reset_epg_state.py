#!/usr/bin/env python3
"""
Reset EPG state: clear authority caches, invalidate timelines, trigger playout rebuild.
"""
import asyncio
import sys

sys.path.insert(0, str(__file__).rsplit("/", 2)[0] or ".")


async def main() -> None:
    from exstreamtv.database import get_sync_session_factory
    from exstreamtv.scheduling.authority import get_authority
    from exstreamtv.tasks.playout_tasks import rebuild_playouts_task
    from exstreamtv.cache.manager import get_cache

    factory = get_sync_session_factory()
    auth = get_authority(factory)

    auth.invalidate_all_timelines()
    print("Cleared authority caches (_timelines, _clocks, _anchor_times)")

    cache = await get_cache()
    await cache.invalidate_epg()
    print("Invalidated EPG cache")

    await rebuild_playouts_task()
    print("Triggered playout rebuild")

    auth.invalidate_all_timelines()
    print("Post-rebuild: invalidate_all_timelines()")


if __name__ == "__main__":
    asyncio.run(main())
