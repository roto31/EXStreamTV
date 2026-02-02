#!/usr/bin/env python3
"""
EXStreamTV Version Bump Tool

Synchronizes version numbers across the platform when releasing new versions.
Follows Semantic Versioning 2.0.0 (https://semver.org)

Usage:
    python scripts/version_bump.py <new_version> [--component <name>]
    python scripts/version_bump.py 2.6.0
    python scripts/version_bump.py 2.5.1 --component api

Options:
    --component    Only bump a specific component's version
    --dry-run      Show what would change without making changes
    --help         Show this help message
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# All component VERSION file locations
COMPONENT_PATHS = {
    "backend_core": PROJECT_ROOT / "exstreamtv" / "VERSION",
    "api": PROJECT_ROOT / "exstreamtv" / "api" / "VERSION",
    "ai_agent": PROJECT_ROOT / "exstreamtv" / "ai_agent" / "VERSION",
    "streaming": PROJECT_ROOT / "exstreamtv" / "streaming" / "VERSION",
    "ffmpeg": PROJECT_ROOT / "exstreamtv" / "ffmpeg" / "VERSION",
    "database": PROJECT_ROOT / "exstreamtv" / "database" / "VERSION",
    "playout": PROJECT_ROOT / "exstreamtv" / "playout" / "VERSION",
    "media": PROJECT_ROOT / "exstreamtv" / "media" / "VERSION",
    "templates": PROJECT_ROOT / "exstreamtv" / "templates" / "VERSION",
    "cache": PROJECT_ROOT / "exstreamtv" / "cache" / "VERSION",
    "tasks": PROJECT_ROOT / "exstreamtv" / "tasks" / "VERSION",
    "integration": PROJECT_ROOT / "exstreamtv" / "integration" / "VERSION",
    "hdhomerun": PROJECT_ROOT / "exstreamtv" / "hdhomerun" / "VERSION",
    "importers": PROJECT_ROOT / "exstreamtv" / "importers" / "VERSION",
    "metadata": PROJECT_ROOT / "exstreamtv" / "metadata" / "VERSION",
    "middleware": PROJECT_ROOT / "exstreamtv" / "middleware" / "VERSION",
    "utils": PROJECT_ROOT / "exstreamtv" / "utils" / "VERSION",
    "validation": PROJECT_ROOT / "exstreamtv" / "validation" / "VERSION",
    "services": PROJECT_ROOT / "exstreamtv" / "services" / "VERSION",
    "scheduling": PROJECT_ROOT / "exstreamtv" / "scheduling" / "VERSION",
    "media_sources": PROJECT_ROOT / "exstreamtv" / "media_sources" / "VERSION",
    "transcoding": PROJECT_ROOT / "exstreamtv" / "transcoding" / "VERSION",
    "static": PROJECT_ROOT / "exstreamtv" / "static" / "VERSION",
    "macos_app": PROJECT_ROOT / "EXStreamTVApp" / "VERSION",
    "scripts": PROJECT_ROOT / "scripts" / "VERSION",
    "tests": PROJECT_ROOT / "tests" / "VERSION",
    "docs": PROJECT_ROOT / "docs" / "VERSION",
    "distributions": PROJECT_ROOT / "distributions" / "VERSION",
    "containers": PROJECT_ROOT / "containers" / "VERSION",
}


def validate_version(version: str) -> bool:
    """Validate version string follows SemVer format."""
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$"
    return bool(re.match(pattern, version))


def read_version_file(path: Path) -> dict:
    """Read a VERSION file and return its contents as a dict."""
    if not path.exists():
        return {}
    
    data = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
    return data


def write_version_file(path: Path, data: dict) -> None:
    """Write a VERSION file from a dict."""
    with open(path, "w") as f:
        for key, value in data.items():
            f.write(f"{key}={value}\n")


def bump_component_version(
    component: str,
    new_version: str,
    platform_version: str,
    dry_run: bool = False
) -> bool:
    """Bump a single component's version."""
    path = COMPONENT_PATHS.get(component)
    if not path:
        print(f"  ⚠️  Unknown component: {component}")
        return False
    
    if not path.exists():
        print(f"  ⚠️  VERSION file not found: {path}")
        return False
    
    data = read_version_file(path)
    old_version = data.get("VERSION", "unknown")
    
    data["VERSION"] = new_version
    data["LAST_MODIFIED"] = date.today().isoformat()
    data["PLATFORM_COMPATIBILITY"] = platform_version
    
    if dry_run:
        print(f"  📝 Would update {component}: {old_version} → {new_version}")
    else:
        write_version_file(path, data)
        print(f"  ✅ Updated {component}: {old_version} → {new_version}")
    
    return True


def bump_root_version(new_version: str, dry_run: bool = False) -> bool:
    """Update the root VERSION file."""
    path = PROJECT_ROOT / "VERSION"
    
    if dry_run:
        print(f"  📝 Would update root VERSION to {new_version}")
    else:
        with open(path, "w") as f:
            f.write(f"{new_version}\n")
        print(f"  ✅ Updated root VERSION to {new_version}")
    
    return True


def bump_pyproject_version(new_version: str, dry_run: bool = False) -> bool:
    """Update the version in pyproject.toml."""
    path = PROJECT_ROOT / "pyproject.toml"
    
    if not path.exists():
        print("  ⚠️  pyproject.toml not found")
        return False
    
    content = path.read_text()
    
    # Update version = "X.Y.Z" line
    pattern = r'version = "[^"]+"'
    replacement = f'version = "{new_version}"'
    
    new_content = re.sub(pattern, replacement, content, count=1)
    
    if dry_run:
        print(f"  📝 Would update pyproject.toml version to {new_version}")
    else:
        path.write_text(new_content)
        print(f"  ✅ Updated pyproject.toml version to {new_version}")
    
    return True


def bump_build_version(new_version: str, dry_run: bool = False) -> bool:
    """Update the Build folder version."""
    build_dir = PROJECT_ROOT / "Build" / f"v{new_version}"
    version_file = build_dir / "VERSION"
    
    if dry_run:
        print(f"  📝 Would create Build/v{new_version}/VERSION")
    else:
        build_dir.mkdir(parents=True, exist_ok=True)
        with open(version_file, "w") as f:
            f.write(f"{new_version}\n")
        print(f"  ✅ Created Build/v{new_version}/VERSION")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="EXStreamTV Version Bump Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("version", help="New version number (e.g., 2.6.0)")
    parser.add_argument(
        "--component",
        help="Only bump a specific component",
        choices=list(COMPONENT_PATHS.keys())
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without making changes"
    )
    
    args = parser.parse_args()
    
    # Validate version format
    if not validate_version(args.version):
        print(f"❌ Invalid version format: {args.version}")
        print("   Expected format: MAJOR.MINOR.PATCH (e.g., 2.6.0)")
        sys.exit(1)
    
    new_version = args.version
    
    print(f"\n🚀 EXStreamTV Version Bump Tool")
    print(f"   New version: {new_version}")
    if args.dry_run:
        print("   Mode: DRY RUN (no changes will be made)\n")
    else:
        print()
    
    success = True
    
    if args.component:
        # Bump single component
        print(f"Updating component: {args.component}")
        success = bump_component_version(
            args.component, new_version, new_version, args.dry_run
        )
    else:
        # Bump all components
        print("Updating root version files...")
        success &= bump_root_version(new_version, args.dry_run)
        success &= bump_pyproject_version(new_version, args.dry_run)
        success &= bump_build_version(new_version, args.dry_run)
        
        print("\nUpdating component version files...")
        for component in COMPONENT_PATHS:
            success &= bump_component_version(
                component, new_version, new_version, args.dry_run
            )
    
    print()
    if success:
        if args.dry_run:
            print("✅ Dry run complete. No changes were made.")
        else:
            print(f"✅ Version bump to {new_version} complete!")
            print("\nNext steps:")
            print("  1. Update CHANGELOG.md with release notes")
            print("  2. Run: python scripts/release.py --prepare")
            print("  3. Commit and tag the release")
    else:
        print("⚠️  Some updates failed. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
