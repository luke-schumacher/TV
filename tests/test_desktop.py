"""Desktop safety, window event dispatch, and real mpv protocol checks."""
import queue
import shutil
import subprocess
import time
import wave
from pathlib import Path

import pytest

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.desktop import DesktopPlayer
from nostalgiabox.player import END_EOF, MockPlayer
from nostalgiabox.config import config_from_dict
from nostalgiabox.app import TVApp


def test_missing_mpv_has_actionable_error(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="brew install mpv"):
        DesktopPlayer()


def test_window_keys_and_close_route_to_app_queue():
    player = object.__new__(DesktopPlayer)
    player._events = queue.Queue()
    player._suppress = False
    inputs, ends = [], []
    player.on_input = inputs.append
    player.on_end = ends.append
    for event in [
        {"event": "client-message", "args": ["tv-key", "KEY_UP"]},
        {"event": "client-message", "args": ["tv-key", "KEY_2"]},
        {"event": "client-message", "args": ["tv-quit"]},
        {"event": "end-file", "reason": "eof", "generation": 0},
    ]:
        player._events.put(event)
    player.poll_events()
    assert inputs == [InputEvent(Action.CHANNEL_UP), InputEvent.digit(2), InputEvent(Action.QUIT)]
    assert ends == [END_EOF]


def test_desktop_api_never_enables_host_shutdown(tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    (show / "ep.mp4").touch()
    config = config_from_dict({"media_root": str(tmp_path), "power_off_on_min_volume": True})
    app = TVApp.from_config(config, player=MockPlayer(), desktop=True)
    assert app.config.power_off_on_min_volume is False
    assert app.config.volume_control == "pi"
    assert app.input.backends == []


@pytest.fixture
def native_player(monkeypatch):
    if not shutil.which("mpv"):
        pytest.skip("native mpv is not installed")
    real_popen = subprocess.Popen
    def headless(args, **kwargs):
        return real_popen([*args, "--vo=null", "--ao=null", "--terminal=no"], **kwargs)
    monkeypatch.setattr(subprocess, "Popen", headless)
    player = DesktopPlayer()
    yield player
    process = player._process
    root = Path(player._temp.name)
    player.close()
    player.close()
    assert process.poll() is not None
    assert not player._reader.is_alive()
    assert not root.exists()


def test_real_mpv_playback_input_eof_and_cleanup(native_player, tmp_path):
    player = native_player
    media = tmp_path / "test.wav"
    with wave.open(str(media), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 4000)
    events, ends = [], []
    player.on_input = events.append
    player.on_end = ends.append
    player.set_volume(37)
    player.set_mute(True)
    assert player._command("get_property", "volume") == 37
    assert player._command("get_property", "mute") is True
    player._command("keypress", "UP")
    player.play(media)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and (not ends or not events):
        player.poll_events()
        time.sleep(0.02)
    assert events == [InputEvent(Action.CHANNEL_UP)]
    assert ends == [END_EOF]
    assert player.get_time_pos() is not None
    player.stop()
    player._command("script-message", "tv-quit")
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and len(events) < 2:
        player.poll_events()
        time.sleep(0.02)
    assert events[-1] == InputEvent(Action.QUIT)


def test_desktop_check_needs_no_python_mpv_or_systemd(tmp_path):
    import io
    from nostalgiabox.doctor import run_check
    show = tmp_path / 'Show'
    show.mkdir()
    (show / 'episode.mp4').touch()
    config = config_from_dict({'media_root': str(tmp_path)})
    out = io.StringIO()
    def forbidden():
        pytest.fail('Desktop must not probe Pi bindings or services')
    result = run_check(config, tmp_path / 'config.yaml', desktop=True,
                       which=lambda name: '/bin/mpv' if name == 'mpv' else None,
                       python_mpv=forbidden, service=forbidden, out=out)
    assert result == 0
    assert 'Start with: nostalgiabox --desktop' in out.getvalue()
