"""Small offline demo library, isolated from the user's normal TV config."""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
import yaml
from .storage import atomic_write


def prepare_demo(root=None):
    root = Path(root) if root else Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'nostalgiabox' / 'demo-v1'
    binary = shutil.which('ffmpeg', path=os.environ.get('PATH', '') + os.pathsep + '/opt/homebrew/bin:/usr/local/bin')
    if not binary:
        raise RuntimeError('The demo needs ffmpeg. macOS: brew install ffmpeg; Ubuntu/Debian: sudo apt install ffmpeg')
    channels = [
        ('Color Lab', 'smptebars=size=960x540:rate=24', 220),
        ('Motion Lab', 'testsrc2=size=960x540:rate=24', 330),
        ('Pattern Lab', 'testsrc=size=960x540:rate=24', 440),
    ]
    for name, source, frequency in channels:
        folder = root / 'Channels' / name
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'Welcome - TV demo.mp4'
        if target.exists() and target.stat().st_size > 0:
            continue
        temporary = folder / '.generating.mp4'
        try:
            subprocess.run([binary, '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'lavfi', '-i', source, '-f', 'lavfi', '-i', f'sine=frequency={frequency}:sample_rate=48000',
                '-t', '18', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                '-af', 'volume=0.12', '-c:a', 'aac', '-movflags', '+faststart', str(temporary)],
                check=True, capture_output=True, text=True, timeout=90)
            temporary.replace(target)
        except (subprocess.SubprocessError, OSError) as exc:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f'Could not generate the demo video: {exc}') from exc
    config = root / 'config.yaml'
    # A demo has its own settings and bookmarks. Never replace a normal config.
    if not config.exists():
        atomic_write(config, yaml.safe_dump({'schema_version': 1, 'media_root': str((root / 'Channels').resolve()),
            'prefer_usb': False, 'tune_in': 'resume', 'order': 'in_order', 'start_offset': 0,
            'initial_volume': 15, 'volume_control': 'pi', 'power_off_on_min_volume': False,
            'state_file': str((root / 'playback.json').resolve()), 'ui': {'theme': 'modern'}}))
    return config
