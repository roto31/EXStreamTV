---
name: design-pattern-decision-tree
description: >-
  Structured methodology for selecting the correct design pattern based on the
  specific pain point in code.  Covers the three-branch decision tree
  (Creational, Structural, Behavioural), the pattern-to-pain-point mapping,
  and the anti-patterns to avoid.  Use when writing new code, reviewing
  existing code, or refactoring — in both the Python/FastAPI backend and the
  React/Vite frontend.
---

# Design-Pattern Decision Tree

## When to Apply

- Creating a new module, service, or component and considering which pattern to use
- Reviewing code that introduces or changes a design pattern
- Refactoring code with observable pain points (complex constructors, conditional cascades, leaky abstractions)
- Answering "which pattern should I use here?" — always start from the tree

## Core Rule

**Identify the pain point first, then walk the decision tree to the correct pattern.**
Never select a pattern by name and look for a place to apply it.

---

## The Three Branches

### Branch 1 — Creational (Object Creation Pain)

**Root question:** Is the pain about *creating* objects?

Symptoms:
- Constructor has 5+ parameters, many optional
- `if/elif` or `match` to decide which class to instantiate
- Defaults are unclear, scattered across callers, or duplicated
- Expensive initialisation is repeated unnecessarily

Decision sub-tree:

```
Creation pain?
├── Many optional params / complex assembly
│   └── Builder (validate on .build())
├── Conditional class selection
│   └── Factory Method or Abstract Factory
├── Single shared instance
│   └── Singleton (use sparingly — prefer DI)
├── Expensive or deferred init
│   └── Lazy Initialization
└── Clone with variation
    └── Prototype
```

**EXStreamTV examples:**
- `TranscodeConfig` dataclass with 10 optional fields → Builder would help (currently a dataclass, acceptable)
- `get_ffmpeg_builder(mode)` → Factory Method ✅ (already correct)
- `get_url_resolver()` module-level global → Lazy Singleton ✅ (already correct)

---

### Branch 2 — Structural (Composition / Interface Pain)

**Root question:** Is the pain about *how objects fit together*?

Symptoms:
- Internal details of a subsystem leak into callers
- Two interfaces don't match but need to interoperate
- Adding optional behaviour requires subclassing
- A subsystem is complex and needs a single entry point

Decision sub-tree:

```
Structure pain?
├── Interface mismatch
│   └── Adapter (translation only — no business logic!)
├── Complex subsystem needs simple entry
│   └── Facade
├── Optional behaviour layers
│   └── Decorator (no interdependent wrappers)
├── Access control / caching indirection
│   └── Proxy
└── Tree of uniform components
    └── Composite
```

**EXStreamTV examples:**
- `_resolved_to_stream_source()` converts ResolvedURL → StreamSource → Adapter ✅
- `StreamingContractEnforcer` validates before FFmpeg → Facade ✅
- `StreamUrlProxy.get_url()` for refreshed URLs → Proxy ✅
- React: ChannelDetailPage decomposed into PlayoutsSection / NowPlayingSection / TimelineSection → Composite ✅

---

### Branch 3 — Behavioural (Conditional / Algorithm Pain)

**Root question:** Is the pain about *behaviour that changes*?

Symptoms:
- Growing if/elif/switch cascade (one branch per type/mode)
- Algorithm varies at runtime (swap strategy based on config)
- Object's behaviour depends on its current state/mode
- Need to notify multiple listeners of an event
- Identical lifecycle with varying details (fetch → error → render)

Decision sub-tree:

```
Behaviour pain?
├── if/elif cascade selecting algorithm
│   └── Strategy (keyed registry, eliminate conditionals)
├── Object behaviour changes with mode
│   └── State (finite modes, defined transitions)
├── Ordered try-then-delegate fallback
│   └── Chain of Responsibility
├── Fan-out notifications
│   └── Observer / Event Bus
├── Deferred / queued operations
│   └── Command
├── Save and restore state
│   └── Memento
└── Identical structure, varying detail
    └── Template Method (Python: ABC; React: custom hook)
```

**EXStreamTV examples:**
- `_detect_source_type` 10+ fallback detectors → Chain of Responsibility ✅ (refactored in `source_type_detector.py`)
- `resolve_sequence_item` 9 directive types → Strategy registry ✅ (refactored in `directive_handlers.py`)
- Channel stream lifecycle → State pattern ✅ (`patterns/state/stream_states.py`)
- `StreamEventBus` → Observer ✅
- `StreamCommandQueue` → Command ✅
- `ScheduleMemento` → Memento ✅
- React: useAsync hook eliminates duplicated fetch boilerplate → Template Method ✅

---

## Pattern-to-Pain-Point Quick Reference

| Pattern | Branch | Pain Signal | Anti-Pattern If Used Without Pain |
|---------|--------|-------------|----------------------------------|
| Builder | Creational | 5+ constructor params, many optional | Over-engineering simple dataclasses |
| Factory | Creational | if/elif to pick class | Factory for single concrete class |
| Singleton | Creational | Must be exactly one instance | "Easy access" to global state |
| Adapter | Structural | Interface A ≠ Interface B | Adapter containing business logic |
| Facade | Structural | Callers need simplified API | Facade hiding useful flexibility |
| Decorator | Structural | Optional behaviour layers | Order-dependent, interdependent wrappers |
| Proxy | Structural | Access control / caching | Proxy doing more than delegation |
| Composite | Structural | Tree of similar objects | Composite for flat, non-hierarchical data |
| Strategy | Behavioural | if/elif per algorithm | Strategy with one implementation |
| State | Behavioural | Mode-driven transitions | State for unbounded/ad-hoc modes |
| Chain of Resp. | Behavioural | Ordered try → delegate | Chain for single handler |
| Observer | Behavioural | Fan-out event notification | Observer with no unsubscribe |
| Command | Behavioural | Deferred/queued operations | Command for synchronous calls |
| Memento | Behavioural | Save/restore object state | Memento for immutable data |
| Template Method | Behavioural | Same structure, different details | Template for unrelated code |

---

## Anti-Patterns to Reject

1. **Singleton for "easy access"** — Use dependency injection. Module-level globals with `get_*()` are acceptable in Python but should not proliferate.

2. **Pattern as aesthetic upgrade** — "Let's add a Decorator for elegance" without a pain point is over-engineering.

3. **Decorator with interdependent wrappers** — If wrapper A must be applied before wrapper B, the design is fragile. Consider a Pipeline or Builder instead.

4. **Factory for a single concrete class** — Direct instantiation is simpler and more readable.

5. **Observer without unsubscribe** — Memory leaks and ghost callbacks. Always pair `subscribe` with `unsubscribe` or `unsubscribe_all`.

6. **Strategy that doesn't eliminate the conditional** — If the original if/elif still exists alongside the Strategy, the refactoring is incomplete.

---

## Verification Checklist

When reviewing or generating pattern code:

- [ ] Pain point is stated explicitly before the pattern is named
- [ ] The decision tree path is traceable (Branch → Sub-question → Pattern)
- [ ] Adapters contain only translation logic
- [ ] Builders validate on `.build()`
- [ ] Strategies replace (not supplement) the original conditional
- [ ] State transitions are finite and documented
- [ ] Observers have unsubscribe mechanisms
- [ ] React hooks follow the Template Method idiom for lifecycle extraction
- [ ] No pattern is applied without a real, observable pain point

---

## Related Rules and Skills

- Enforcement rule: `.cursor/rules/design-pattern-decision-tree.mdc`
- Existing patterns: `.cursor/rules/patterns-implemented.mdc`
- Safety rules: `.cursor/rules/exstreamtv-critical.mdc`
- Codebase expert: `.cursor/skills/exstreamtv-expert/SKILL.md`
