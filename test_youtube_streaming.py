#!/usr/bin/env python3
"""
Test whether YouTube can be used for streaming in EXStreamTV.

Resolves a public YouTube video to a streamable URL via yt-dlp.
Run: python3 test_youtube_streaming.py
"""

import asyncio
import sys
from types import SimpleNamespace


async def main() -> int:
    print("=== YouTube Streaming Test ===\n")

    # 1. Check yt-dlp
    try:
        import yt_dlp
        print("✓ yt-dlp installed")
    except ImportError:
        print("✗ yt-dlp not installed. Install with: pip install yt-dlp")
        return 1

    # 2. Resolve a public video (Rick Astley - public, no age gate)
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    media_item = SimpleNamespace(url=test_url, id=1, source="youtube")

    print(f"Resolving: {test_url}")
    print("(This may take 10-20 seconds)...\n")

    try:
        from exstreamtv.streaming.url_resolver import get_url_resolver

        resolver = get_url_resolver()
        resolved = await resolver.resolve(media_item)

        if not resolved or not resolved.url:
            print("✗ Failed: No stream URL returned")
            return 1

        print("✓ Resolved to streamable URL")
        print(f"  URL (truncated): {resolved.url[:80]}...")
        print(f"  Expires: {resolved.expires_at}")
        if resolved.metadata:
            title = resolved.metadata.get("title", "N/A")
            duration = resolved.metadata.get("duration", "N/A")
            print(f"  Title: {title}")
            print(f"  Duration: {duration}s")

        # 3. Verify URL is reachable (HEAD request)
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.head(
                    resolved.url,
                    headers=resolved.headers or {},
                    follow_redirects=True,
                )
                if resp.status_code in (200, 302, 301):
                    print("\n✓ Stream URL is reachable (HTTP %d)" % resp.status_code)
                else:
                    print(f"\n? Stream URL returned HTTP {resp.status_code}")

        except ImportError:
            print("\n  (Install httpx to verify URL reachability)")
        except Exception as e:
            print(f"\n? Could not verify URL: {e}")

        print("\n=== YouTube streaming is working ===\n")
        return 0

    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
