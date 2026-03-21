#!/usr/bin/env python3
"""
EXStreamTV Fix Applicator
Applies the Plex tuning + EPG title fixes directly to source files.
Run from the EXStreamTV root directory:
    python3 apply_fixes.py
"""

import re
import sys
from pathlib import Path


def fix_plex_resolver(path: Path) -> bool:
    """Fix: prefer config/cache tokens over expired URL-embedded tokens."""
    text = path.read_text()

    # Check if already fixed
    if "url_token" in text and "Last resort" in text:
        print(f"  [skip] {path.name} — already patched")
        return False

    # Replace the _extract_plex_info method's URL token extraction + fallback chain.
    # Match from "Try to extract from URL" through "return info" at the end of the method.
    old = re.compile(
        r"(        # Try to extract from URL\n"
        r"        url = self\._get_url\(media_item\)\n"
        r"        if url:\n"
        r"            import re\n"
        r".*?"  # everything in between
        r")(        return info)",
        re.DOTALL,
    )

    replacement = (
        "        # Extract rating_key and server_url from the stored URL.\n"
        "        # The token extracted here is from import time and likely EXPIRED,\n"
        "        # so we store it separately and only use it as a last resort.\n"
        "        url = self._get_url(media_item)\n"
        "        url_token = None\n"
        "        if url:\n"
        "            import re\n"
        "            match = re.search(r\"/library/metadata/(\\d+)\", url)\n"
        "            if match:\n"
        "                info[\"rating_key\"] = match.group(1)\n"
        "            \n"
        "            match = re.search(r\"(https?://[^/]+)\", url)\n"
        "            if match and not info.get(\"server_url\"):\n"
        "                info[\"server_url\"] = match.group(1)\n"
        "            \n"
        "            # Save URL-embedded token separately — it's stale from import time\n"
        "            match = re.search(r\"X-Plex-Token=([^&]+)\", url)\n"
        "            if match:\n"
        "                url_token = match.group(1)\n"
        "        \n"
        "        # Now look for FRESH tokens from authoritative sources (library cache,\n"
        "        # global config). These are maintained by the user and take priority\n"
        "        # over expired tokens embedded in imported URLs.\n"
        "        \n"
        "        # Source 1: Library cache (per-library server_url + token)\n"
        "        _load_plex_library_cache()\n"
        "        \n"
        "        library_id = getattr(media_item, \"library_id\", None)\n"
        "        if library_id and library_id in _plex_library_cache:\n"
        "            lib_info = _plex_library_cache[library_id]\n"
        "            if not info.get(\"server_url\"):\n"
        "                info[\"server_url\"] = lib_info[\"server_url\"]\n"
        "            if not info.get(\"token\"):\n"
        "                info[\"token\"] = lib_info[\"token\"]\n"
        "            logger.debug(f\"Using Plex credentials from cached library {library_id}: {lib_info['name']}\")\n"
        "        \n"
        "        # Source 2: First available Plex library from cache\n"
        "        if not info.get(\"token\"):\n"
        "            if _plex_first_library_cache:\n"
        "                lib_info = _plex_first_library_cache\n"
        "                if not info.get(\"server_url\"):\n"
        "                    info[\"server_url\"] = lib_info[\"server_url\"]\n"
        "                info[\"token\"] = lib_info[\"token\"]\n"
        "                logger.debug(f\"Using Plex credentials from first cached library: {lib_info['name']}\")\n"
        "        \n"
        "        # Source 3: Global config\n"
        "        if not info.get(\"token\"):\n"
        "            try:\n"
        "                from exstreamtv.config import get_config\n"
        "                config = get_config()\n"
        "                \n"
        "                plex_config = getattr(config, 'plex', None)\n"
        "                if plex_config:\n"
        "                    if not info.get(\"server_url\"):\n"
        "                        info[\"server_url\"] = getattr(plex_config, 'url', '') or getattr(plex_config, 'base_url', '')\n"
        "                    if not info.get(\"token\"):\n"
        "                        info[\"token\"] = getattr(plex_config, 'token', '')\n"
        "                \n"
        "                libraries_plex = getattr(getattr(config, 'libraries', None), 'plex', None)\n"
        "                if libraries_plex:\n"
        "                    if not info.get(\"server_url\"):\n"
        "                        info[\"server_url\"] = getattr(libraries_plex, 'url', '')\n"
        "                    if not info.get(\"token\"):\n"
        "                        info[\"token\"] = getattr(libraries_plex, 'token', '')\n"
        "                \n"
        "                if info.get(\"token\"):\n"
        "                    logger.debug(\"Using Plex credentials from global config\")\n"
        "            except Exception as e:\n"
        "                logger.warning(f\"Failed to load Plex config: {e}\")\n"
        "        \n"
        "        # Last resort: use the token embedded in the stored URL (likely expired)\n"
        "        if not info.get(\"token\") and url_token:\n"
        "            info[\"token\"] = url_token\n"
        "            logger.debug(\"Using Plex token from stored URL (may be expired)\")\n"
        "        \n"
        "        return info"
    )

    new_text, count = old.subn(replacement.replace("\\", "\\\\"), text)
    if count == 0:
        print(f"  [WARN] {path.name} — pattern not found, applying manual fix")
        # Simpler approach: just replace the token extraction line
        if 'info["token"] = match.group(1)' in text and "url_token" not in text:
            # Replace the direct token assignment with url_token capture
            text = text.replace(
                '            # Extract token\n'
                '            match = re.search(r"X-Plex-Token=([^&]+)", url)\n'
                '            if match:\n'
                '                info["token"] = match.group(1)',
                '            # Save URL-embedded token separately — stale from import time\n'
                '            match = re.search(r"X-Plex-Token=([^&]+)", url)\n'
                '            if match:\n'
                '                url_token = match.group(1)'
            )
            # Add url_token initialization before the URL block
            text = text.replace(
                '        # Try to extract from URL\n'
                '        url = self._get_url(media_item)',
                '        # Try to extract from URL\n'
                '        url_token = None\n'
                '        url = self._get_url(media_item)'
            )
            # Change fallback conditions to always check for fresh token
            text = text.replace(
                '        # FALLBACK 1: Try library_id',
                '        # PRIORITY 1: Try library_id (fresh token)'
            )
            text = text.replace(
                '        # FALLBACK 2: Try first available',
                '        # PRIORITY 2: Try first available'
            )
            text = text.replace(
                '        # FALLBACK 3: If still missing',
                '        # PRIORITY 3: Global config'
            )
            # Remove the condition that skips fallbacks when URL token exists
            for old_cond in [
                'if not info.get("server_url") or not info.get("token"):',
            ]:
                # Only change the ones guarding the token fallback, keep server_url checks
                pass
            
            # Add last-resort url_token usage before return
            text = text.replace(
                '        return info',
                '        # Last resort: use URL-embedded token (likely expired)\n'
                '        if not info.get("token") and url_token:\n'
                '            info["token"] = url_token\n'
                '            logger.debug("Using Plex token from stored URL (may be expired)")\n'
                '        \n'
                '        return info',
                1  # Only first occurrence
            )
            path.write_text(text)
            print(f"  [OK] {path.name} — applied manual token priority fix")
            return True
        else:
            print(f"  [FAIL] {path.name} — could not apply fix automatically")
            return False

    path.write_text(new_text)
    print(f"  [OK] {path.name} — token priority fixed")
    return True


def fix_epg_titles(path: Path) -> bool:
    """Fix: filter 'Item NNNNNN' placeholder titles from all sources."""
    text = path.read_text()

    if "^Item \\d+$" in text:
        print(f"  [skip] {path.name} — already has Item filter")
        return False

    # Ensure 'import re' is at the top
    if "\nimport re\n" not in text:
        text = text.replace(
            "import logging\n",
            "import logging\nimport re\n",
            1,
        )

    changes = 0

    # Fix the XMLTV EPG path: custom_title priority with placeholder filter
    old_xmltv = (
        '                title = schedule_item.get("custom_title")\n'
        '                if not title:\n'
        '                    # Get media item title, handling None safely\n'
        '                    title = media_item.title if (media_item and media_item.title) else None'
    )
    new_xmltv = (
        '                custom_title = schedule_item.get("custom_title")\n'
        '                title = custom_title\n'
        '                if not title:\n'
        '                    title = media_item.title if (media_item and media_item.title) else None\n'
        '\n'
        '                # Skip placeholder titles from importers (e.g. "Item 332245")\n'
        '                if title and re.match(r"^Item \\d+$", title):\n'
        '                    real_title = None\n'
        '                    if media_item:\n'
        '                        real_title = (\n'
        '                            getattr(media_item, "original_title", None)\n'
        '                            or getattr(media_item, "sort_title", None)\n'
        '                            or getattr(media_item, "episode_title", None)\n'
        '                        )\n'
        '                        if not real_title:\n'
        '                            series = getattr(media_item, "series_title", None) or getattr(media_item, "show_title", None)\n'
        '                            if series:\n'
        '                                ep = getattr(media_item, "episode_title", None)\n'
        '                                real_title = f"{series} - {ep}" if ep else series\n'
        '                    title = real_title if real_title else None'
    )

    if old_xmltv in text:
        text = text.replace(old_xmltv, new_xmltv, 1)
        changes += 1

    # Also fix M3U path if present
    old_m3u = 'title = schedule_item.get("custom_title") or media_item.title'
    if old_m3u in text:
        new_m3u = (
            'custom_title = schedule_item.get("custom_title")\n'
            '                title = custom_title or media_item.title\n'
            '                # Skip placeholder titles from importers\n'
            '                if title and re.match(r"^Item \\d+$", title):\n'
            '                    title = (\n'
            '                        getattr(media_item, "original_title", None)\n'
            '                        or getattr(media_item, "sort_title", None)\n'
            '                        or getattr(media_item, "episode_title", None)\n'
            '                        or media_item.title\n'
            '                    )'
        )
        text = text.replace(old_m3u, new_m3u, 1)
        changes += 1

    if changes:
        path.write_text(text)
        print(f"  [OK] {path.name} — {changes} EPG title filter(s) applied")
        return True
    else:
        print(f"  [WARN] {path.name} — title patterns not found (file may differ)")
        return False


def fix_channel_manager(path: Path) -> bool:
    """Fix: advance item index on failure + keep-alive for empty playout."""
    text = path.read_text()
    changes = 0

    # Fix 1: advance item index on URL resolution failure
    old_error = (
        '        except Exception as e:\n'
        '            logger.error(f"Error getting next playout item: {e}")\n'
        '            return None'
    )
    new_error = (
        '        except Exception as e:\n'
        '            logger.error(\n'
        '                f"Error getting next playout item at index {self._current_item_index} "\n'
        '                f"for channel {self.channel_number}: {e}"\n'
        '            )\n'
        '            self._current_item_index += 1\n'
        '            return None'
    )

    if "self._current_item_index += 1" not in text.split("Error getting next playout item")[0] + text.split("Error getting next playout item")[-1]:
        if old_error in text:
            text = text.replace(old_error, new_error, 1)
            changes += 1

    # Fix 2: send keep-alive null packets when no content
    old_wait = (
        '                    # No content available - show offline slate or wait\n'
        '                    logger.debug(\n'
        '                        f"No content for channel {self.channel_number}, waiting..."\n'
        '                    )\n'
        '                    await asyncio.sleep(5.0)\n'
        '                    continue'
    )
    new_wait = (
        '                    logger.warning(\n'
        '                        f"Channel {self.channel_number}: no playable content. "\n'
        '                        f"Check media source connectivity (Plex token, server URL, etc.)"\n'
        '                    )\n'
        '                    null_packet = bytes([0x47, 0x1F, 0xFF, 0x10] + [0xFF] * 184)\n'
        '                    for _ in range(7):\n'
        '                        await self._broadcast_chunk(null_packet)\n'
        '                    await asyncio.sleep(5.0)\n'
        '                    continue'
    )

    if old_wait in text:
        text = text.replace(old_wait, new_wait, 1)
        changes += 1

    if changes:
        path.write_text(text)
        print(f"  [OK] {path.name} — {changes} fix(es) applied")
        return True
    else:
        print(f"  [skip] {path.name} — fixes already applied or patterns differ")
        return False


def cleanup_debug_logs(root: Path) -> int:
    """Remove #region agent log blocks from all source files."""
    count = 0
    for pyfile in root.rglob("*.py"):
        if ".build" in str(pyfile) or "venv" in str(pyfile):
            continue
        text = pyfile.read_text()
        if "# #region agent log" not in text:
            continue

        # Remove blocks: # #region agent log ... # #endregion (with surrounding blank lines)
        new_text = re.sub(
            r'\n?\s*# #region agent log\n.*?# #endregion\n?',
            '\n',
            text,
            flags=re.DOTALL,
        )
        # Also remove standalone blocks without #endregion (try/except pattern)
        new_text = re.sub(
            r'\n\s*# #region agent log\n\s*try:\n\s*import json[^\n]*\n.*?except:\s*pass\n',
            '\n',
            new_text,
            flags=re.DOTALL,
        )

        if new_text != text:
            pyfile.write_text(new_text)
            count += 1
            print(f"  [OK] {pyfile.relative_to(root)} — debug logs removed")

    return count


def main():
    root = Path(".")

    # Verify we're in the right directory
    if not (root / "exstreamtv").is_dir():
        print("ERROR: Run this from the EXStreamTV root directory")
        sys.exit(1)

    print("EXStreamTV Fix Applicator")
    print("=" * 50)

    print("\n1. Fixing Plex resolver (expired token priority)...")
    plex_path = root / "exstreamtv" / "streaming" / "resolvers" / "plex.py"
    if plex_path.exists():
        fix_plex_resolver(plex_path)
    else:
        print(f"  [WARN] {plex_path} not found")

    print("\n2. Fixing EPG titles ('Item NNNNNN' placeholders)...")
    iptv_path = root / "exstreamtv" / "api" / "iptv.py"
    if iptv_path.exists():
        fix_epg_titles(iptv_path)
    else:
        print(f"  [WARN] {iptv_path} not found")

    print("\n3. Fixing channel manager (stuck items + keep-alive)...")
    cm_path = root / "exstreamtv" / "streaming" / "channel_manager.py"
    if cm_path.exists():
        fix_channel_manager(cm_path)
    else:
        print(f"  [WARN] {cm_path} not found")

    print("\n4. Cleaning up debug log instrumentation...")
    cleaned = cleanup_debug_logs(root / "exstreamtv")
    if cleaned == 0:
        print("  [skip] No debug log blocks found")

    print("\n" + "=" * 50)
    print("Done. Restart EXStreamTV to apply changes:")
    print("  ./stop.sh && ./start.sh")


if __name__ == "__main__":
    main()
