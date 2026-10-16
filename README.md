# TV

A public fork of [NostalgiaBox](https://github.com/landonbtw/NostalgiaBox), bringing its folder-based retro television experience to Linux desktops and macOS. The upstream MIT license and Raspberry Pi implementation are retained.

Each show folder becomes a channel. Change channels, shuffle episodes, resume a series, or simulate an always-on broadcast. CRT curvature and the green retro overlays remain optional.

## Desktop setup

Requires Python 3.9+ and the native **mpv executable**. Desktop mode uses mpv JSON IPC and a native Qt setup/settings panel; neither python-mpv nor evdev is required. The installer adds the optional `desktop` extra. macOS 13+ is required by current Qt wheels.

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

Launch TV and use **Choose folder → Review channels → Watch**. If a saved config exists, TV goes straight to your show. Press **S** for settings and change the library at any time. You can also edit `config.yaml` directly. Make one subfolder per show and add your own videos:

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

macOS automatically selects desktop mode; use `--desktop` on Linux. `-c /path/to/config.yaml` selects a different config. Existing configurations remain compatible. Desktop mode always disables host shutdown, selects software volume, and removes the Pi preload delay. A missing library opens setup; a disconnected drive shows a recoverable message with S to open settings; background scans detect additions and removals every ten seconds. Discovered channel numbers stay stable as folders are added. It does not install boot services or require input-device permissions.

## Try it first

```sh
.venv/bin/nostalgiabox --demo
```

This generates three short test channels with quiet audio tones, using ffmpeg (`brew install ffmpeg` or `sudo apt install ffmpeg` if needed). Demo videos, settings, and bookmarks stay in a separate cache folder; your normal TV configuration is preserved. Press G for the guide, S for settings, and Q to quit.

## Controls

Focus the TV window first. USB remotes that behave as keyboards work through the same window bindings.

| Key | Action |
| --- | --- |
| Up / Down, Page Up / Page Down | Next / previous channel |
| Left / Right, - / + | Volume |
| 0–9, Enter | Tune to channel number |
| M | Mute |
| I | Channel and episode banner |
| G | Channel guide |
| S | Settings |
| L | Last channel |
| P | Standby / wake |
| F | Fullscreen |
| Escape | Close guide, or quit when guide is closed |
| Q, close window | Quit TV |

Press **G** for the channel guide: Up/Down selects, Enter tunes, Escape returns to the current show. **S** opens modeless settings while playback continues. Settings include library/channel forms, exclusions, audio output, Modern/CRT preview, text scale, high contrast, and reduced motion. Cancel restores previews, and validated settings save atomically with a backup of legacy configs.

Desktop input is local to the window. Pi `input.key_overrides` apply to evdev only. Desktop switches cut directly to the next show; preloading and static transitions use the base player's immediate fallback. No claim of seamless desktop preloading is made.

## Raspberry Pi

The original Linux console / remote / HDMI-CEC setup remains in [the upstream Pi guide](docs/RASPBERRY_PI.md), with the existing `scripts/install.sh` and `.[pi]` extra. That guide retains upstream URLs for reference; use this checkout if you want the TV changes. `--desktop` is optional on Linux so Pi users keep their existing behavior.

## Development and verification

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,desktop]'
.venv/bin/python -m pytest
```

The suite includes real mpv IPC smoke tests when mpv is installed. They use synthetic media and null audio/video outputs, so they do not prove hardware decoding, speaker output, or a visible window. GitHub Actions runs on Ubuntu and macOS with Python 3.9 and 3.13 and installs native mpv. A manual graphical check should include channel switching, overlays, mute, fullscreen, EOF advance, and window-close cleanup.

The [implementation plan](docs/IMPLEMENTATION_PLAN.md) records the implemented stages. See [release and graphical acceptance](docs/RELEASE.md) for wheel/native bundles and the remaining signing/hardware gates. The original [proposal](docs/PROPOSAL.md) preserves the design rationale.

Use `--settings` to open the control panel at launch. `--no-ui` runs the lightweight player without Qt forms; the guide and viewing controls still work, while S has no settings panel in this mode.

`questionbox/` is a separate upstream ESP32/AI project. It is preserved but is not part of the TV desktop runtime or this port's validation.
