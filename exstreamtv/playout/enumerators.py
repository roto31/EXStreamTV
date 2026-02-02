"""
Collection enumerators for playout scheduling.

Ported from ErsatzTV *CollectionEnumerator.cs files.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, Iterator, List, Optional, TypeVar

T = TypeVar("T")


class CollectionEnumerator(ABC, Generic[T]):
    """
    Base class for collection enumerators.

    Enumerators determine the order in which media items are played.
    """

    def __init__(self, items: List[T], state: Optional[Dict[str, Any]] = None):
        self.items = items
        self._index = 0
        if state:
            self.restore_state(state)

    @abstractmethod
    def get_next(self) -> Optional[T]:
        """Get the next item in the collection."""
        pass

    def peek_next(self) -> Optional[T]:
        """Peek at the next item without advancing."""
        if not self.items:
            return None
        return self.items[self._index % len(self.items)]

    def get_state(self) -> Dict[str, Any]:
        """Get the current enumerator state for persistence."""
        return {
            "index": self._index,
            "seed": getattr(self, "_seed", None),
        }

    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore enumerator state from persistence."""
        self._index = state.get("index", 0)
        if "seed" in state and state["seed"] is not None:
            self._seed = state["seed"]

    @property
    def is_empty(self) -> bool:
        """Check if the collection is empty."""
        return len(self.items) == 0

    @property
    def count(self) -> int:
        """Get the number of items."""
        return len(self.items)

    def reset(self) -> None:
        """Reset the enumerator to the beginning."""
        self._index = 0


class ChronologicalEnumerator(CollectionEnumerator[T]):
    """
    Enumerate items in order (by sort key, then original order).

    Ported from ErsatzTV ChronologicalMediaCollectionEnumerator.cs.
    """

    def __init__(
        self,
        items: List[T],
        sort_key: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
    ):
        # Sort items if sort_key provided
        if sort_key:
            items = sorted(items, key=lambda x: getattr(x, sort_key, 0))
        super().__init__(items, state)

    def get_next(self) -> Optional[T]:
        """Get the next item in chronological order."""
        if not self.items:
            return None

        item = self.items[self._index % len(self.items)]
        self._index += 1
        return item


class ShuffledEnumerator(CollectionEnumerator[T]):
    """
    Enumerate items in shuffled order.

    Ported from ErsatzTV ShuffledMediaCollectionEnumerator.cs.
    """

    def __init__(
        self,
        items: List[T],
        seed: Optional[int] = None,
        state: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(items, state)
        self._seed = seed or random.randint(0, 2**32 - 1)
        self._shuffled: List[T] = []
        self._reshuffle()

    def _reshuffle(self) -> None:
        """Reshuffle the collection."""
        rng = random.Random(self._seed)
        self._shuffled = self.items.copy()
        rng.shuffle(self._shuffled)

    def get_next(self) -> Optional[T]:
        """Get the next item in shuffled order."""
        if not self._shuffled:
            return None

        item = self._shuffled[self._index % len(self._shuffled)]
        self._index += 1

        # Reshuffle when we've gone through all items
        if self._index >= len(self._shuffled):
            self._index = 0
            self._seed += 1
            self._reshuffle()

        return item

    def get_state(self) -> Dict[str, Any]:
        """Get state including seed for consistent shuffles."""
        state = super().get_state()
        state["seed"] = self._seed
        return state


class RandomEnumerator(CollectionEnumerator[T]):
    """
    Enumerate items randomly (with possible repeats).

    Ported from ErsatzTV RandomizedMediaCollectionEnumerator.cs.
    """

    def __init__(
        self,
        items: List[T],
        avoid_repeats: bool = True,
        state: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(items, state)
        self._avoid_repeats = avoid_repeats
        self._last_index: Optional[int] = None

    def get_next(self) -> Optional[T]:
        """Get a random item."""
        if not self.items:
            return None

        if len(self.items) == 1:
            return self.items[0]

        # Avoid immediate repeats if configured
        if self._avoid_repeats and self._last_index is not None:
            available_indices = [
                i for i in range(len(self.items)) if i != self._last_index
            ]
            idx = random.choice(available_indices)
        else:
            idx = random.randint(0, len(self.items) - 1)

        self._last_index = idx
        self._index += 1
        return self.items[idx]

    def get_state(self) -> Dict[str, Any]:
        """Get state including last index."""
        state = super().get_state()
        state["last_index"] = self._last_index
        return state

    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore state including last index."""
        super().restore_state(state)
        self._last_index = state.get("last_index")


class RotatingShuffledEnumerator(CollectionEnumerator[T]):
    """
    Shuffled enumerator that rotates through groups.

    Ported from ErsatzTV RandomizedRotatingMediaCollectionEnumerator.cs.
    """

    def __init__(
        self,
        items: List[T],
        group_key: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(items, state)
        self._group_key = group_key
        self._groups: Dict[Any, List[T]] = {}
        self._group_order: List[Any] = []
        self._group_index = 0
        self._item_indices: Dict[Any, int] = {}

        self._build_groups()

    def _build_groups(self) -> None:
        """Group items and shuffle within groups."""
        if not self._group_key:
            self._groups = {"default": self.items.copy()}
            random.shuffle(self._groups["default"])
        else:
            for item in self.items:
                key = getattr(item, self._group_key, "default")
                if key not in self._groups:
                    self._groups[key] = []
                self._groups[key].append(item)

            # Shuffle within each group
            for group in self._groups.values():
                random.shuffle(group)

        self._group_order = list(self._groups.keys())
        random.shuffle(self._group_order)

        # Initialize item indices
        for key in self._groups:
            self._item_indices[key] = 0

    def get_next(self) -> Optional[T]:
        """Get the next item, rotating through groups."""
        if not self._groups:
            return None

        # Get current group
        group_key = self._group_order[self._group_index % len(self._group_order)]
        group = self._groups[group_key]

        # Get item from group
        item_idx = self._item_indices[group_key] % len(group)
        item = group[item_idx]

        # Advance indices
        self._item_indices[group_key] = item_idx + 1
        self._group_index += 1
        self._index += 1

        return item
