"""Immutable presentation snapshots: UI reads these, actions change the app."""
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ChannelView:
    number: int
    name: str
    episode: str
    position: float = 0
    duration: Optional[float] = None
    watching: bool = False

@dataclass(frozen=True)
class ViewingSnapshot:
    state: str
    channels: tuple[ChannelView, ...]
    selected: int
    volume: int
    muted: bool
    error: Optional[str] = None
    search_query: str = ""
    search_active: bool = False
    total_channels: int = 0
