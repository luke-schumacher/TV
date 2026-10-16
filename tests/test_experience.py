import json
import queue
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.config import ConfigError, config_from_dict
from nostalgiabox.settings import SettingsDraft, read_document
from nostalgiabox.library import DurationCache, LibraryService, stable_config
from nostalgiabox.player import PlaybackEvent, END_ERROR, END_EOF, PlayerCapabilities
from nostalgiabox.playback_state import PlaybackState
from tests.test_app import build_app, send


def library(tmp_path):
    root = tmp_path / 'Library'
    (root / 'Zebra').mkdir(parents=True)
    (root / 'Zebra' / 'ep.mp4').touch()
    return root


def test_settings_invalid_save_preserves_bytes_and_unknown_fields(tmp_path):
    root = library(tmp_path)
    path = tmp_path / 'config.yaml'
    original = {'media_root': str(root), 'extension': {'future': 123}, 'ui': {'future_option': 'keep'}}
    path.write_text(yaml.safe_dump(original))
    before = path.read_bytes()
    draft = SettingsDraft(path)
    draft.update({'channels': [{'number': 2, 'path': str(root / 'Zebra')}, {'number': 2, 'path': str(root / 'Zebra')}]})
    with pytest.raises(ConfigError, match='duplicate'):
        draft.save()
    assert path.read_bytes() == before
    draft.data.pop('channels')
    draft.update({'ui': {'scale': 1.2}})
    draft.save()
    saved = read_document(path)
    assert saved['extension'] == {'future': 123}
    assert saved['ui']['future_option'] == 'keep'
    assert saved['schema_version'] == 1
    assert path.with_suffix('.yaml.v0.bak').read_bytes() == before


def test_settings_concurrent_edits_and_future_schema_are_protected(tmp_path):
    root = library(tmp_path)
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump({'media_root': str(root)}))
    draft = SettingsDraft(path)
    path.write_text(path.read_text() + '\nexternal: true\n')
    with pytest.raises(ConfigError, match='another window'):
        draft.save()
    path.write_text('schema_version: 99\n')
    with pytest.raises(ConfigError, match='Unsupported'):
        SettingsDraft(path)


def test_channel_numbers_stay_stable_when_show_is_added(tmp_path):
    root = library(tmp_path)
    registry = tmp_path / 'channels.json'
    config = stable_config(config_from_dict({'media_root': str(root)}), registry)
    assert config.channels[0].number == 2
    (root / 'Arthur').mkdir()
    (root / 'Arthur' / 'ep.mp4').touch()
    again = stable_config(config_from_dict({'media_root': str(root)}), registry)
    assert {c.name: c.number for c in again.channels} == {'Arthur': 3, 'Zebra': 2}


def test_duration_cache_invalidates_changed_files(tmp_path, monkeypatch):
    import nostalgiabox.library as mod
    media = tmp_path / 'ep.mp4'
    media.write_bytes(b'a')
    calls = []
    monkeypatch.setattr(mod, 'probe_duration', lambda path, timeout: calls.append(path) or 20)
    cache = DurationCache(tmp_path / 'cache.json')
    assert cache.probe(media) == 20
    assert cache.probe(media) == 20
    assert len(calls) == 1
    cache.save()
    assert DurationCache(cache.path).get(media) == 20
    media.write_bytes(b'changed')
    assert cache.get(media) is None
    assert cache.probe(media) == 20
    assert len(calls) == 2


def test_guide_navigation_keeps_current_show_until_enter(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    current = player.current
    send(app, Action.GUIDE)
    send(app, Action.CHANNEL_DOWN)
    assert player.current == current
    assert app.guide_index == 1
    assert '> 03' in player.overlays[5]
    send(app, Action.ENTER)
    assert app.lineup.current.number == 3
    assert not app.guide_open
    send(app, Action.GUIDE)
    send(app, Action.BACK)
    assert not app.guide_open
    assert app.lineup.current.number == 3


def test_stale_playback_generation_and_error_backoff(tmp_path):
    app, player, clock = build_app(tmp_path)
    app.start()
    player.generation = 8
    before = len(player.played)
    app._ended.put(PlaybackEvent(END_EOF, 7))
    app.step()
    assert len(player.played) == before
    app._ended.put(PlaybackEvent(END_ERROR, 8))
    app.step()
    assert len(player.played) == before
    assert app.error
    clock.advance(3)
    app.step()
    assert len(player.played) == before + 1


def test_player_without_preload_cuts_immediately(tmp_path):
    app, player, _ = build_app(tmp_path, bridge_seconds=5)
    player.capabilities = PlayerCapabilities()
    app.start()
    send(app, Action.CHANNEL_UP)
    assert app._switch_deadline is None
    assert player.preloaded is None
    assert len(player.played) == 2


def test_future_state_version_is_not_overwritten(tmp_path):
    path = tmp_path / 'state.json'
    original = '{"version":99,"channels":{}}'
    path.write_text(original)
    state = PlaybackState.load(path)
    state.save()
    assert path.read_text() == original


def test_scan_skips_hidden_and_supports_cancellation(tmp_path):
    from nostalgiabox.channel import scan_episodes
    root = library(tmp_path)
    hidden = root / 'Zebra' / '.hidden'
    hidden.mkdir()
    (hidden / 'secret.mp4').touch()
    assert len(scan_episodes(root, ['.mp4'])) == 1
    assert scan_episodes(root, ['.mp4'], cancelled=lambda: True) == []
