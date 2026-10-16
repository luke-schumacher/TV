# TV

A public fork of [NostalgiaBox](https://github.com/landonbtw/NostalgiaBox), bringing its folder-based retro television experience to Linux desktops and macOS. The upstream MIT license and Raspberry Pi implementation are retained.

Each show folder becomes a channel. Change channels, shuffle episodes, resume a series, or simulate an always-on broadcast. CRT curvature and the green retro overlays remain optional.

## Desktop setup

Requires Python 3.9+ and the native **mpv executable**. Desktop mode uses mpv JSON IPC; neither python-mpv nor evdev is required.

macOS (Apple Silicon or Intel, with [Homebrew](https://brew.sh)):

```sh
brew install python mpv
```

Debian/Ubuntu desktop:

```sh
sudo apt update
sudo apt install python3 python3-venv mpv
```

On Fedora install `python3` and `mpv` using your configured repositories; on Arch install `python` and `mpv`. Linux needs an active graphical desktop session (X11 or Wayland).

From this checkout:

```sh
bash scripts/install-desktop.sh
```

Edit `config.yaml`: set `media_root` to your library, for example `~/Movies/TV` on Mac or `~/Videos/TV` on Linux. Make one subfolder per show and add your own videos:

```text
TV/
  Arthur/
    S01E01.mp4
    S01E02.mp4
  Dragon Tales/
    Episode 1.mkv
```

```sh
.venv/bin/nostalgiabox --desktop --check
.venv/bin/nostalgiabox --desktop
# Optional fullscreen at launch:
.venv/bin/nostalgiabox --desktop --fullscreen
```

macOS automatically selects desktop mode; use `--desktop` on Linux. `-c /path/to/config.yaml` selects a different config. Existing configurations remain compatible. Desktop mode always disables host shutdown, selects software volume, and removes the Pi preload delay. It does not install boot services or require input-device permissions.

## Controls

Focus the TV window first. USB remotes that behave as keyboards work through the same window bindings.

| Key | Action |
| --- | --- |
| Up / Down, Page Up / Page Down | Next / previous channel |
| Left / Right, - / + | Volume |
| 0–9, Enter | Tune to channel number |
| M | Mute |
| I | Channel banner |
| L | Last channel |
| P | Standby / wake |
| F | Fullscreen |
| Q / Escape, close window | Quit TV |

Desktop input is local to the window. Pi `input.key_overrides` apply to evdev only. Desktop switches cut directly to the next show; preloading and static transitions use the base player's immediate fallback. No claim of seamless desktop preloading is made.

## Raspberry Pi

The original Linux console / remote / HDMI-CEC setup remains in [the upstream Pi guide](docs/RASPBERRY_PI.md), with the existing `scripts/install.sh` and `.[pi]` extra. That guide retains upstream URLs for reference; use this checkout if you want the TV changes. `--desktop` is optional on Linux so Pi users keep their existing behavior.

## Development and verification

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
```

The suite includes real mpv IPC smoke tests when mpv is installed. They use synthetic media and null audio/video outputs, so they do not prove hardware decoding, speaker output, or a visible window. GitHub Actions runs on Ubuntu and macOS with Python 3.9 and 3.13 and installs native mpv. A manual graphical check should include channel switching, overlays, mute, fullscreen, EOF advance, and window-close cleanup.

UI and architecture proposals, tradeoffs, and suggested delivery order are in [docs/PROPOSAL.md](docs/PROPOSAL.md).

`questionbox/` is a separate upstream ESP32/AI project. It is preserved but is not part of the TV desktop runtime or this port's validation.
