# EXStreamTV Import Timeout Troubleshooting

## Error

```
TimeoutError: [Errno 60] Operation timed out
```

Occurs when running `python3 -m exstreamtv` during import of `exstreamtv.database`, at `importlib._bootstrap_external.get_data` (reading module file from disk).

## Root Cause

**`TimeoutError` when reading local files** typically means the project lives on:

1. **iCloud Drive** – With "Optimize Mac Storage", files may be cloud-only until first access; the download can time out
2. **Network / external drive** – Slow or unreliable storage
3. **Sync or antivirus** – Scanning or syncing can block file reads

Your project path: `/Users/roto1231/Documents/XCode Projects/EXStreamTV`

On macOS, `~/Documents` is often synced with iCloud, which can trigger this.

## Solutions

### 1. Force Download of Project in iCloud (if used)

1. Open **Finder** → **Documents** → **XCode Projects** → **EXStreamTV**
2. Right‑click the **EXStreamTV** folder
3. If you see **"Download Now"**, choose it and wait for all files to download
4. Or: **System Settings** → **Apple ID** → **iCloud** → **iCloud Drive** → **Options** → ensure Documents is set as you want, or turn off **Optimize Mac Storage** for this Mac

### 2. Move Project to Local‑Only Storage (Recommended)

Move the project to a directory that is not synced to iCloud:

```bash
mkdir -p ~/Projects
mv "/Users/roto1231/Documents/XCode Projects/EXStreamTV" ~/Projects/
cd ~/Projects/EXStreamTV
python3 -m exstreamtv
```

Then use `~/Projects/EXStreamTV` as your project root.

### 3. Check File Access

Confirm files are readable without delay:

```bash
# Quick read test
time cat "/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv/database/__init__.py" > /dev/null
```

If this is slow (several seconds) or hangs, the storage or sync setup is the issue.

## Verify the Fix

After applying one of the solutions:

```bash
cd /path/to/EXStreamTV  # Use your chosen path
python3 debug_import.py
```

You should see:

```
Importing exstreamtv.main...
OK - main imported
```

**Last Revised:** 2026-03-20
