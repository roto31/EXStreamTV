"""
Base filter classes for FFmpeg pipeline.

Ported from ErsatzTV BaseFilter.cs and FilterChain.cs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from exstreamtv.ffmpeg.state.frame_state import FrameState


class BaseFilter(ABC):
    """
    Abstract base class for FFmpeg filters.

    Ported from ErsatzTV BaseFilter.cs.
    """

    @property
    def global_options(self) -> List[str]:
        """Global FFmpeg options for this filter."""
        return []

    @property
    def filter_options(self) -> List[str]:
        """Filter-specific options."""
        return []

    @property
    def output_options(self) -> List[str]:
        """Output options for this filter."""
        return []

    @property
    @abstractmethod
    def filter_string(self) -> str:
        """The FFmpeg filter string (e.g., 'scale=1920:1080')."""
        pass

    @abstractmethod
    def next_state(self, current_state: FrameState) -> FrameState:
        """
        Calculate the next frame state after applying this filter.

        Args:
            current_state: Current frame state.

        Returns:
            Updated frame state.
        """
        pass

    def is_applicable(self, current_state: FrameState) -> bool:
        """
        Check if this filter should be applied given the current state.

        Args:
            current_state: Current frame state.

        Returns:
            True if filter should be applied.
        """
        return True


@dataclass
class FilterChain:
    """
    A chain of FFmpeg filters that can be combined.

    Ported from ErsatzTV FilterChain.cs.
    """

    video_filters: List[BaseFilter] = field(default_factory=list)
    audio_filters: List[BaseFilter] = field(default_factory=list)

    def add_video_filter(self, filter_: BaseFilter) -> "FilterChain":
        """Add a video filter to the chain."""
        self.video_filters.append(filter_)
        return self

    def add_audio_filter(self, filter_: BaseFilter) -> "FilterChain":
        """Add an audio filter to the chain."""
        self.audio_filters.append(filter_)
        return self

    def build_video_filter_string(self) -> Optional[str]:
        """Build the combined video filter string."""
        if not self.video_filters:
            return None

        filter_strings = [
            f.filter_string
            for f in self.video_filters
            if f.filter_string
        ]
        return ",".join(filter_strings) if filter_strings else None

    def build_audio_filter_string(self) -> Optional[str]:
        """Build the combined audio filter string."""
        if not self.audio_filters:
            return None

        filter_strings = [
            f.filter_string
            for f in self.audio_filters
            if f.filter_string
        ]
        return ",".join(filter_strings) if filter_strings else None

    def build_complex_filter(self) -> Optional[str]:
        """
        Build a complex filtergraph for multiple streams.

        Returns:
            Complex filter string or None.
        """
        parts = []

        video_str = self.build_video_filter_string()
        if video_str:
            parts.append(f"[0:v]{video_str}[v]")

        audio_str = self.build_audio_filter_string()
        if audio_str:
            parts.append(f"[0:a]{audio_str}[a]")

        if not parts:
            return None

        return ";".join(parts)

    def get_filter_args(self) -> List[str]:
        """
        Get FFmpeg arguments for filters.

        Returns:
            List of FFmpeg arguments.
        """
        args = []

        video_str = self.build_video_filter_string()
        if video_str:
            args.extend(["-vf", video_str])

        audio_str = self.build_audio_filter_string()
        if audio_str:
            args.extend(["-af", audio_str])

        return args

    def apply_to_state(self, initial_state: FrameState) -> FrameState:
        """
        Apply all filters and return the final state.

        Args:
            initial_state: Starting frame state.

        Returns:
            Final frame state after all filters.
        """
        state = initial_state

        for filter_ in self.video_filters:
            state = filter_.next_state(state)

        for filter_ in self.audio_filters:
            state = filter_.next_state(state)

        return state
