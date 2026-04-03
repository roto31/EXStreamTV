from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContentItem:
    ref: str
    genre: str
    show_id: str


@dataclass
class SchedulingPersona:
    genre_weights: dict[str, float] = field(default_factory=dict)


class SchedulingStrategy(ABC):
    @abstractmethod
    def order_content(
        self, items: list[ContentItem], persona: SchedulingPersona
    ) -> list[ContentItem]:
        ...


class BalancedStrategy(SchedulingStrategy):
    def order_content(
        self, items: list[ContentItem], persona: SchedulingPersona
    ) -> list[ContentItem]:
        return sorted(
            items,
            key=lambda x: (-persona.genre_weights.get(x.genre, 0.0), x.show_id),
        )


class VarietyStrategy(SchedulingStrategy):
    def order_content(
        self, items: list[ContentItem], persona: SchedulingPersona
    ) -> list[ContentItem]:
        if not items:
            return []
        by_genre: dict[str, list[ContentItem]] = {}
        for it in items:
            by_genre.setdefault(it.genre, []).append(it)
        for g in by_genre:
            random.shuffle(by_genre[g])
        out: list[ContentItem] = []
        genres = list(by_genre.keys())
        random.shuffle(genres)
        i = 0
        while sum(len(v) for v in by_genre.values()) > 0:
            g = genres[i % len(genres)]
            stack = by_genre.get(g, [])
            if stack:
                out.append(stack.pop())
            i += 1
        return out


class PrimetimeHeavyStrategy(SchedulingStrategy):
    def order_content(
        self, items: list[ContentItem], persona: SchedulingPersona
    ) -> list[ContentItem]:
        weights = dict(persona.genre_weights)
        weights.setdefault("drama", 1.0)
        weights.setdefault("comedy", 0.9)
        adj = SchedulingPersona(genre_weights=weights)
        return BalancedStrategy().order_content(items, adj)


_STRATEGIES: dict[str, type[SchedulingStrategy]] = {
    "balanced": BalancedStrategy,
    "variety": VarietyStrategy,
    "primetime_heavy": PrimetimeHeavyStrategy,
}


def get_scheduling_strategy(style: str) -> SchedulingStrategy:
    key = (style or "balanced").lower().replace("-", "_")
    cls = _STRATEGIES.get(key, BalancedStrategy)
    return cls()
