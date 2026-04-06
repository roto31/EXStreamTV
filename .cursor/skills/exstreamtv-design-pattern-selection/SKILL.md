---
name: exstreamtv-design-pattern-selection
description: Select GoF-style design patterns using a three-branch pain-point decision tree for EXStreamTV (FastAPI + React). Use when refactoring services, API clients, FFmpeg builders, stream FSM, or frontend data loading; when reviewing pattern misuse; or when choosing Strategy vs State vs Chain.
---

# EXStreamTV — design pattern selection (decision tree)

## When to use

- Adding or refactoring Python services, FastAPI routers, `exstreamtv/patterns/*`, or `frontend/src/*`.
- Choosing between Strategy, State, Command, Chain, Factory, Facade, or Adapter.
- Reviewing whether an existing “pattern” folder matches the actual problem.

## Process (mandatory)

1. **Name the pain point** in one sentence (creation vs structure vs behavior).
2. Walk the **correct branch** below until one outcome fits.
3. If no outcome fits, **do not** force a named pattern — use plain functions or smaller modules.
4. Prefer **existing** project homes (`exstreamtv/patterns/`, `StreamService`, `fetchJson`) over new pattern types.

## Branch A — Creational

**Root:** Need to create/configure objects?

| Question | Answer | Pattern |
|----------|--------|---------|
| How many instances? | One only | Singleton — **only** for true single-instance resources; in FastAPI prefer `app.state` / lifespan wiring, not import-time globals |
| Multiple + complex construction (many params, steps) | Yes | **Builder** (e.g. FFmpeg argv builders) |
| Multiple + who picks concrete type? | Subclass / per-type policy | **Factory Method** / registry factory (e.g. `get_ffmpeg_builder(mode)`) |
| Multiple + families of related products | Need family | **Abstract Factory** (rare; use when several objects must vary together) |
| Multiple + clone from prototype | Clone existing | **Prototype** (copy configs/templates) |

## Branch B — Structural

**Root:** Need to structure relationships / boundaries?

| Goal | Pattern |
|------|---------|
| Match incompatible interfaces | **Adapter** (HTTP client ↔ domain types; **translation only**) |
| Simplify a large subsystem | **Facade** (`StreamService`, thin API modules) |
| Add behavior without subclassing | **Decorator** (use sparingly; avoid order-dependent stacks) |
| Control access (lazy, auth, cache) | **Proxy** (`StreamUrlProxy`) |
| Tree / hierarchy | **Composite** |
| Share immutable flyweight data | **Flyweight** |
| Swap implementations behind an abstraction | **Bridge** |

## Branch C — Behavioral

**Root:** Need to vary algorithms, requests, or collaboration?

| What behavior? | Pattern |
|------------------|---------|
| Pass along until handled | **Chain of Responsibility** (`URLResolver.resolve_or_pass`) |
| Encapsulate action + undo/redo | **Command** (`StreamCommandQueue`) |
| Traverse without exposing internals | **Iterator** |
| Centralize many-to-many talking | **Mediator** |
| Snapshot / restore | **Memento** (schedule history / snapshots) |
| Broadcast events | **Observer** / event bus |
| Behavior follows explicit mode | **State** (`ChannelContext` / `StreamState`) |
| Swap algorithm at runtime | **Strategy** (scheduling strategies, builder registry) |
| Fixed steps, varying hooks | **Template Method** (hook: React `useAsyncResource` loader) |
| Operations over a structure | **Visitor** (rare in this codebase) |

## Anti-patterns

- **Singleton** as a global grab-bag (use DI / `app.state`).
- **Decorator** chains where order is implicit and fragile.
- **Adapter** containing business rules or DB access.
- **Strategy** that is really one branch — keep as a function until a second branch appears.
- Patterns for **appearance** without a matching pain point.

## Repo anchors

- **State / Command / Factory / Chain / Strategy / Mediator / Observer / Proxy / Memento:** `exstreamtv/patterns/` and `AGENTS.md` pattern section.
- **HTTP boundary:** `frontend/src/api/client.ts`, `exstreamtv/api/*`.
- **Enforcement rule:** `.cursor/rules/exstreamtv-design-pattern-selection.mdc`.
