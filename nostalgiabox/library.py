"""Cancellable background library scans and persistent metadata.

Workers never mutate the application or Qt widgets. A completed snapshot is
reconciled on the main thread. Duration probes have a bounded four-worker pool.
"""
from __future__ import annotations
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from .channel import build_lineup, scan_episodes
from .config import load_config, ConfigError
from .playback_state import default_state_path
from .probe import probe_duration
from .storage import write_json


class DurationCache:
    def __init__(self, path=None):
        self.path = path or default_state_path().with_name('durations.json')
        self._lock = threading.Lock()
        try:
            raw = json.loads(self.path.read_text())
            self.values = raw.get('entries', {}) if raw.get('version') == 1 else {}
            if not isinstance(self.values, dict):
                self.values = {}
        except (OSError, ValueError, AttributeError):
            self.values = {}

    def key(self, path):
        try:
            stat = path.stat()
            return f'{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}'
        except OSError:
            return None

    def get(self, path):
        key = self.key(path)
        with self._lock:
            value = self.values.get(key)
        return value if isinstance(value, (int, float)) and value > 0 else None

    def probe(self, path):
        key = self.key(path)
        if key is None:
            return None
        with self._lock:
            if key in self.values:
                return self.get_unlocked(key)
        value = probe_duration(path, timeout=3)
        with self._lock:
            self.values[key] = value
        return value

    def get_unlocked(self, key):
        value = self.values.get(key)
        return value if isinstance(value, (int, float)) and value > 0 else None

    def save(self):
        with self._lock:
            # Bound growth; old mtime keys are harmless and eventually evicted.
            payload = dict(list(self.values.items())[-20000:])
        write_json(self.path, {'version': 1, 'entries': payload})


def stable_config(config, registry_path=None):
    """Discovery numbers persist across new folders; explicit YAML numbers win."""
    if config.media_source == 'channels':
        return config
    path = registry_path or default_state_path().with_name('channels.json')
    try:
        raw = json.loads(path.read_text())
        numbers = raw['channels'] if raw.get('version') == 1 else {}
        if not isinstance(numbers, dict):
            numbers = {}
    except (OSError, ValueError, KeyError, AttributeError):
        numbers = {}
    numbers = {k: v for k, v in numbers.items() if isinstance(k, str) and type(v) is int and v >= 0}
    used = set(numbers.values())
    channels = []
    assigned = set()
    for channel in config.channels:
        key = str(channel.path.resolve())
        number = numbers.get(key)
        if number is None or number in assigned:
            number = max(2, min(config.channel_numbers(), default=2))
            while number in used or number in assigned:
                number += 1
            numbers[key] = number
        used.add(number)
        assigned.add(number)
        channels.append(replace(channel, number=number))
    write_json(path, {'version': 1, 'channels': numbers})
    return replace(config, channels=channels)


class LibraryService:
    def __init__(self, cache=None):
        self.cache = cache or DurationCache()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='tv-library')
        self.probes = ThreadPoolExecutor(max_workers=4, thread_name_prefix='tv-probe')
        self.cancelled = threading.Event()
        self.future = None

    def scan(self, path, *, stable=True):
        if self.future is not None and not self.future.done():
            return self.future
        def work():
            config = load_config(path)
            if not config.channels or config.media_error:
                raise ConfigError(config.media_error or 'No show folders found. Reconnect the drive or choose another library.')
            if stable:
                config = stable_config(config)
            episodes = {}
            for ch in config.channels:
                if self.cancelled.is_set():
                    return None
                episodes[ch.path] = scan_episodes(ch.path, config.video_extensions,
                    recursive=config.scan_recursive, exclude=ch.exclude, exclude_seasons=ch.exclude_seasons,
                    cancelled=self.cancelled.is_set)
            if not any(episodes.values()):
                raise ConfigError("No videos available. Reconnect your drive or choose another library.")
            lineup = build_lineup(config, episodes_by_path=episodes, duration_lookup=self.cache.get)
            revision = []
            for ch in lineup:
                for item in ch.episodes:
                    try:
                        stat = item.stat()
                        revision.append((ch.number, str(item), stat.st_size, stat.st_mtime_ns))
                    except OSError:
                        revision.append((ch.number, str(item), None, None))
            lineup.revision = tuple(revision)
            return config, lineup
        self.future = self.executor.submit(work)
        return self.future

    def warm(self, lineup):
        """At most four queued probe loops, rather than one Future per file."""
        paths = [p for ch in lineup for p in ch.episodes]
        def batch(offset):
            for path in paths[offset::4]:
                if self.cancelled.is_set():
                    break
                self.cache.probe(path)
            try:
                self.cache.save()
            except OSError:
                pass
        return [self.probes.submit(batch, i) for i in range(4)]

    def close(self):
        self.cancelled.set()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.probes.shutdown(wait=False, cancel_futures=True)
