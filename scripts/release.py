#!/usr/bin/env python3
"""
EXStreamTV Release Management Tool

Handles release preparation, archive creation, and manifest generation.

Usage:
    python scripts/release.py --prepare
    python scripts/release.py --archive <version>
    python scripts/release.py --manifest
    python scripts/release.py --sync-build

Options:
    --prepare      Prepare current version for release (validate, generate manifest)
    --archive      Archive a version (copy to archive folder)
    --manifest     Regenerate the Build manifest for current version
    --sync-build   Sync current source to Build folder (run after changes)
    --check        Validate version consistency across all files
    --help         Show this help message
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def get_current_version() -> str:
    """Get the current platform version from the root VERSION file."""
    version_file = PROJECT_ROOT / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"


def get_pyproject_version() -> str:
    """Get the version from pyproject.toml."""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return "unknown"
    
    content = pyproject.read_text()
    match = re.search(r'version = "([^"]+)"', content)
    if match:
        return match.group(1)
    return "unknown"


def count_files(directory: Path, pattern: str) -> int:
    """Count files matching a pattern in a directory tree."""
    return len(list(directory.rglob(pattern)))


def check_version_consistency() -> tuple[bool, list[str]]:
    """Check that all version files are consistent."""
    errors = []
    root_version = get_current_version()
    pyproject_version = get_pyproject_version()
    
    if root_version != pyproject_version:
        errors.append(f"VERSION ({root_version}) != pyproject.toml ({pyproject_version})")
    
    # Check component VERSION files
    exstreamtv_dir = PROJECT_ROOT / "exstreamtv"
    for version_file in exstreamtv_dir.rglob("VERSION"):
        content = version_file.read_text()
        match = re.search(r"VERSION=(\S+)", content)
        if match:
            component_version = match.group(1)
            if component_version != root_version:
                rel_path = version_file.relative_to(PROJECT_ROOT)
                errors.append(f"{rel_path}: {component_version} != {root_version}")
    
    return len(errors) == 0, errors


def generate_build_manifest(version: str) -> dict:
    """Generate a build manifest for the specified version."""
    exstreamtv_dir = PROJECT_ROOT / "exstreamtv"
    
    manifest = {
        "version": version,
        "release_date": date.today().isoformat(),
        "status": "current",
        "components": {},
        "file_counts": {
            "python": count_files(exstreamtv_dir, "*.py"),
            "html": count_files(exstreamtv_dir, "*.html"),
            "css": count_files(exstreamtv_dir, "*.css"),
            "js": count_files(exstreamtv_dir, "*.js"),
        },
        "dependencies": [],
    }
    
    # Read dependencies from pyproject.toml
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        deps_match = re.search(r'dependencies = \[(.*?)\]', content, re.DOTALL)
        if deps_match:
            deps_str = deps_match.group(1)
            deps = re.findall(r'"([^"]+)"', deps_str)
            manifest["dependencies"] = deps
    
    # Get component versions
    for version_file in exstreamtv_dir.rglob("VERSION"):
        rel_path = version_file.relative_to(exstreamtv_dir)
        component_name = str(rel_path.parent) if rel_path.parent != Path(".") else "core"
        
        content = version_file.read_text()
        component_data = {}
        for line in content.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                component_data[key.strip()] = value.strip()
        
        manifest["components"][component_name] = component_data
    
    return manifest


def write_manifest_md(version: str, manifest: dict) -> None:
    """Write the manifest as a Markdown file."""
    build_dir = PROJECT_ROOT / "Build" / f"v{version}"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    manifest_path = build_dir / "MANIFEST.md"
    
    content = f"""# EXStreamTV v{version} Build Manifest

**Release Date**: {manifest['release_date']}  
**Status**: {manifest['status'].title()}

## Component Inventory

| Component | Version | Last Modified |
|-----------|---------|---------------|
"""
    
    for name, data in sorted(manifest["components"].items()):
        comp_version = data.get("VERSION", "unknown")
        last_modified = data.get("LAST_MODIFIED", "unknown")
        content += f"| {name} | {comp_version} | {last_modified} |\n"
    
    content += f"""
## File Statistics

| Category | Count |
|----------|-------|
| Python modules | {manifest['file_counts']['python']} |
| HTML templates | {manifest['file_counts']['html']} |
| CSS files | {manifest['file_counts']['css']} |
| JavaScript files | {manifest['file_counts']['js']} |

## Dependencies

"""
    
    for dep in manifest["dependencies"]:
        content += f"- {dep}\n"
    
    manifest_path.write_text(content)
    print(f"  ✅ Generated {manifest_path.relative_to(PROJECT_ROOT)}")


def prepare_release() -> bool:
    """Prepare the current version for release."""
    version = get_current_version()
    
    print(f"\n🚀 Preparing EXStreamTV v{version} for release\n")
    
    # Check version consistency
    print("Checking version consistency...")
    consistent, errors = check_version_consistency()
    if not consistent:
        print("  ❌ Version inconsistencies found:")
        for error in errors:
            print(f"     - {error}")
        print("\n  Run: python scripts/version_bump.py {version} to fix")
        return False
    print("  ✅ All versions are consistent")
    
    # Generate manifest
    print("\nGenerating build manifest...")
    manifest = generate_build_manifest(version)
    write_manifest_md(version, manifest)
    
    # Write JSON manifest as well
    build_dir = PROJECT_ROOT / "Build" / f"v{version}"
    json_path = build_dir / "manifest.json"
    with open(json_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  ✅ Generated {json_path.relative_to(PROJECT_ROOT)}")
    
    print(f"\n✅ Release preparation complete for v{version}!")
    print("\nNext steps:")
    print("  1. Review CHANGELOG.md")
    print("  2. Commit changes: git add -A && git commit -m 'Release v{version}'")
    print("  3. Create tag: git tag -a v{version} -m 'Version {version}'")
    print("  4. Push: git push origin main --tags")
    
    return True


def archive_version(version: str) -> bool:
    """Archive a version to the archive folder."""
    archive_dir = PROJECT_ROOT / "archive" / f"v{version}"
    
    if archive_dir.exists():
        print(f"  ⚠️  Archive already exists: {archive_dir}")
        return False
    
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy VERSION file
    (archive_dir / "VERSION").write_text(f"{version}\n")
    
    # Generate MANIFEST.md
    manifest = generate_build_manifest(version)
    manifest["status"] = "archived"
    write_manifest_md(version, manifest)
    
    print(f"  ✅ Archived version {version} to {archive_dir.relative_to(PROJECT_ROOT)}")
    return True


def sync_build_folder() -> bool:
    """
    Sync current source code to the Build folder.
    
    IMPORTANT: This function uses shutil.copytree() to create REAL FILE COPIES,
    NOT symbolic links. Symlinks are intentionally avoided to prevent breakage
    and ensure each version snapshot is completely self-contained.
    """
    import shutil
    
    version = get_current_version()
    build_dir = PROJECT_ROOT / "Build" / f"v{version}"
    
    print(f"Syncing source to Build/v{version}/...")
    print("  (Using real file copies, NOT symlinks)")
    
    # Directories to sync (will be copied with shutil.copytree, not symlinked)
    dirs_to_sync = [
        "exstreamtv",
        "EXStreamTVApp",
        "scripts",
        "tests",
        "docs",
        "distributions",
        "containers",
    ]
    
    build_dir.mkdir(parents=True, exist_ok=True)
    
    for dirname in dirs_to_sync:
        src = PROJECT_ROOT / dirname
        dst = build_dir / dirname
        
        if src.exists():
            # Remove existing destination (old copy)
            if dst.exists():
                shutil.rmtree(dst)
            
            # Copy directory - creates REAL FILES, not symlinks
            # symlinks=False ensures any symlinks in source are followed and real files are copied
            shutil.copytree(src, dst, symlinks=False)
            print(f"  ✅ Synced {dirname}/ (real copy)")
        else:
            print(f"  ⚠️  Source not found: {dirname}/")
    
    # Update VERSION file
    (build_dir / "VERSION").write_text(f"{version}\n")
    
    # Regenerate manifest
    manifest = generate_build_manifest(version)
    write_manifest_md(version, manifest)
    
    # Write JSON manifest
    json_path = build_dir / "manifest.json"
    with open(json_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n✅ Build folder synced to v{version}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="EXStreamTV Release Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Prepare current version for release"
    )
    parser.add_argument(
        "--archive",
        metavar="VERSION",
        help="Archive a version"
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Regenerate the Build manifest for current version"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate version consistency across all files"
    )
    parser.add_argument(
        "--sync-build",
        action="store_true",
        help="Sync current source to Build folder"
    )
    
    args = parser.parse_args()
    
    if args.prepare:
        success = prepare_release()
        sys.exit(0 if success else 1)
    
    elif args.archive:
        print(f"\n📦 Archiving version {args.archive}\n")
        success = archive_version(args.archive)
        sys.exit(0 if success else 1)
    
    elif args.manifest:
        version = get_current_version()
        print(f"\n📝 Regenerating manifest for v{version}\n")
        manifest = generate_build_manifest(version)
        write_manifest_md(version, manifest)
        sys.exit(0)
    
    elif args.check:
        print("\n🔍 Checking version consistency\n")
        consistent, errors = check_version_consistency()
        if consistent:
            print("  ✅ All versions are consistent")
            sys.exit(0)
        else:
            print("  ❌ Version inconsistencies found:")
            for error in errors:
                print(f"     - {error}")
            sys.exit(1)
    
    elif args.sync_build:
        print("\n🔄 Syncing Build folder\n")
        success = sync_build_folder()
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
