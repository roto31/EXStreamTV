# Confluence Documentation - EXStreamTV v2.6.0

This folder contains documentation formatted for Confluence upload.

## Upload Instructions

### Method 1: Copy/Paste (Simple)
1. Open the `.confluence.md` file
2. Copy the content
3. In Confluence, create a new page
4. Use "Insert" → "Markup" → "Markdown"
5. Paste the content

### Method 2: Import Markdown (Recommended)
1. Install the "Markdown Macro" app in Confluence
2. Create a new page
3. Use the Markdown macro
4. Paste the content from `.confluence.md` files

### Method 3: Confluence REST API
```bash
# Example using curl
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d @page-content.json \
  "https://your-domain.atlassian.net/wiki/rest/api/content"
```

## Mermaid Diagrams in Confluence

### Option 1: Mermaid Macro (Recommended)
Install the "Mermaid Diagrams for Confluence" app, then use:
```
{mermaid}
graph TD
    A --> B
{mermaid}
```

### Option 2: Draw.io Integration
1. Export Mermaid as SVG from mermaid.live
2. Import into Confluence using Draw.io macro

### Option 3: Pre-rendered Images
If Mermaid macros aren't available:
1. Visit https://mermaid.live
2. Paste the Mermaid code
3. Download as PNG/SVG
4. Upload image to Confluence

## File List

| File | Description | Confluence Space |
|------|-------------|------------------|
| `00-HOME.confluence.md` | Documentation home page | Root |
| `01-SYSTEM-DESIGN.confluence.md` | System architecture | Architecture |
| `02-TUNARR-INTEGRATION.confluence.md` | v2.6.0 integration | Architecture |
| `03-API-REFERENCE.confluence.md` | REST API documentation | API |
| `04-STREAMING-STABILITY.confluence.md` | Streaming features | Guides |
| `05-ADVANCED-SCHEDULING.confluence.md` | Scheduling features | Guides |
| `06-AI-SETUP.confluence.md` | AI configuration | Guides |
| `07-QUICK-START.confluence.md` | Getting started | Guides |
| `08-BUILD-PROGRESS.confluence.md` | Development status | Development |

## Suggested Confluence Structure

```
EXStreamTV Documentation (Space)
├── Home
├── Getting Started
│   ├── Quick Start
│   ├── Installation
│   └── Onboarding
├── User Guides
│   ├── AI Setup
│   ├── Streaming Stability
│   ├── Advanced Scheduling
│   ├── Channel Creation
│   └── Local Media
├── Architecture
│   ├── System Design
│   └── Tunarr/dizqueTV Integration
├── API Reference
│   └── REST API
└── Development
    ├── Build Progress
    ├── Contributing
    └── Changelog
```

## Version Info

- **Documentation Version:** 2.6.0
- **Last Updated:** 2026-01-31
- **Generated For:** Confluence Cloud/Server
