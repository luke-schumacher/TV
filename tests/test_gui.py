"""Native form behavior tested offscreen; no display or real library required."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
from pathlib import Path
import pytest
pytest.importorskip('PySide6')
from nostalgiabox.gui import SettingsDialog, application
from nostalgiabox.library import DurationCache

@pytest.fixture(scope='module')
def qt():
    return application()


def wait(qt, dialog):
    deadline = time.monotonic() + 5
    while dialog.future is not None and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(.01)
    assert dialog.future is None


def test_first_run_review_watch_and_cancel(qt, tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    root = tmp_path / 'Library'
    (root / 'Arthur').mkdir(parents=True)
    (root / 'Arthur' / 'ep.mp4').touch()
    path = tmp_path / 'config.yaml'
    saved = []
    dialog = SettingsDialog(path, first_run=True, on_saved=lambda *args: saved.append(args), cache=DurationCache(tmp_path / 'cache'))
    dialog.root.setText(str(root))
    dialog.prepare(save=False)
    wait(qt, dialog)
    assert not path.exists()
    assert dialog.table.rowCount() == 1
    dialog.prepare(save=True)
    wait(qt, dialog)
    assert path.exists()
    assert len(saved) == 1
    before = path.read_bytes()
    cancel = SettingsDialog(path)
    cancel.root.setText('/missing/path')
    cancel.reject()
    assert path.read_bytes() == before


def test_invalid_settings_show_error_without_overwrite(qt, tmp_path):
    path = tmp_path / 'config.yaml'
    dialog = SettingsDialog(path, first_run=True)
    dialog.root.setText('/does-not-exist/tv')
    dialog.prepare(save=True)
    assert 'does not exist' in dialog.status.text()
    assert not path.exists()
    dialog.reject()


def test_relative_paths_and_custom_extensions_survive_save(qt, tmp_path, monkeypatch):
    import yaml
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    shows = tmp_path / 'shows'
    (shows / 'Arthur').mkdir(parents=True)
    (shows / 'Arthur' / 'ep.mp4').touch()
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump({'media_root': './shows', 'channels': [
        {'number': 2, 'path': 'Arthur', 'vendor_option': 42}]}))
    dialog = SettingsDialog(path)
    assert dialog.root.text() == str(shows)
    assert dialog.table.item(0, 2).text() == str(shows / 'Arthur')
    dialog.prepare(save=True)
    wait(qt, dialog)
    saved = yaml.safe_load(path.read_text())
    assert saved['channels'][0]['vendor_option'] == 42
    assert saved['channels'][0]['path'] == str(shows / 'Arthur')


def test_existing_library_has_visible_startup_before_background_scan(qt, tmp_path, monkeypatch):
    from concurrent.futures import Future
    from PySide6.QtCore import QTimer
    from nostalgiabox.gui import DesktopSession
    path = tmp_path / 'config.yaml'
    path.write_text('media_root: /unused\n')
    session = DesktopSession(path)
    monkeypatch.setattr(session.service, 'scan', lambda _: Future())
    QTimer.singleShot(80, qt.quit)
    session.run()
    assert session.loading is not None
    assert session._ticks > 0
    session.loading.accept()
