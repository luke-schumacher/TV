import subprocess
import pytest
import yaml
from nostalgiabox.demo import prepare_demo


def test_demo_is_cached_and_preserves_existing_settings(tmp_path, monkeypatch):
    monkeypatch.setattr('nostalgiabox.demo.shutil.which', lambda *a, **kw: '/bin/ffmpeg')
    calls=[]
    def generate(args, **kwargs):
        calls.append(args)
        from pathlib import Path
        Path(args[-1]).write_bytes(b'demo')
    monkeypatch.setattr(subprocess, 'run', generate)
    path=prepare_demo(tmp_path)
    assert len(calls)==3
    raw=yaml.safe_load(path.read_text())
    assert raw['initial_volume']==15
    assert raw['state_file']==str(tmp_path/'playback.json')
    path.write_text(path.read_text()+'custom: keep\n')
    prepare_demo(tmp_path)
    assert len(calls)==3
    assert yaml.safe_load(path.read_text())['custom']=='keep'


def test_demo_failure_removes_partial_video(tmp_path, monkeypatch):
    monkeypatch.setattr('nostalgiabox.demo.shutil.which', lambda *a, **kw: '/bin/ffmpeg')
    def fail(args, **kwargs):
        from pathlib import Path
        Path(args[-1]).touch()
        raise subprocess.TimeoutExpired('ffmpeg', 90)
    monkeypatch.setattr(subprocess,'run',fail)
    with pytest.raises(RuntimeError,match='generate'):
        prepare_demo(tmp_path)
    assert not list(tmp_path.rglob('*.mp4'))
