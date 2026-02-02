# EXStreamTV v2.1.0 Archive Manifest

**Release Date**: 2026-01-17  
**Status**: AI Channel Creator Personas (Phase 12)

## Summary

New persona system for AI Channel Creator with Sports and Tech expert personas.

## Persona Registry (3 personas)

| ID | Character | Title | Specialties |
|----|-----------|-------|-------------|
| `tv_executive` | Max Sterling | TV Programming Executive | Classic TV, scheduling, dayparts |
| `sports_expert` | Howard "The Stat" Kowalski | Sports Savant | Sports, classic games, YouTube, Archive.org |
| `tech_expert` | Steve "Woz" Nakamura | Tech Savant | Apple, computing, keynotes, retro tech |

## New Files

### Sports Savant Persona
- `exstreamtv/ai_agent/prompts/sports_expert.py`
- Schwab-style sports historian character
- YouTube sports channels registry
- Archive.org sports collections
- Sports documentary series metadata
- Sports movies database

### Tech Savant Persona
- `exstreamtv/ai_agent/prompts/tech_expert.py`
- Apple specialist and tech historian
- Complete Apple keynote archive metadata
- Apple commercials campaign database
- YouTube tech channels registry
- Archive.org tech collections

### Enhanced Prompts Package
- `exstreamtv/ai_agent/prompts/__init__.py` - Persona registry
- `get_persona(persona_id)` function
- `list_personas()` function

## Previous Version

← v2.0.1: Media Filtering & UI Improvements

## Next Version

→ v2.2.0: Complete AI Persona Suite
