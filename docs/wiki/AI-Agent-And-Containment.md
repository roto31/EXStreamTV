# AI Agent & Containment

See [Platform Guide](PLATFORM_GUIDE.md#5-ai-agent--safety-model) for bounded agent, tool execution, risk levels, confidence gating, containment mode, and automatic shutdown.

**Coding-time containment (Cursor):** Runtime AI is bounded by design; edits to `exstreamtv/` are also guarded by overlapping rules (`exstreamtv-safety.mdc`, `exstreamtv-critical.mdc`), `AGENTS.md`, path-local agent files, and `ffmpeg/constants.py`. Overview: [Architecture Diagrams §18](../architecture/DIAGRAMS.md#18-six-layer-ai--coding-safety-enforcement-2026-03--post-merge-main) (wiki: **Architecture-Diagrams**).

**Last Revised:** 2026-03-21
