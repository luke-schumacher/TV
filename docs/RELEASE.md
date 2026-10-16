# TV 1.1 release and graphical acceptance

## Build

```sh
python -m pip install '.[desktop,dev,packaging]'
python -m pytest
python -m build
bash scripts/build-desktop.sh
```

Wheel and sdist outputs go to `dist/`. The desktop bundler creates an unsigned native `TV.app` ZIP on macOS or an executable directory tarball on Linux. These bundles include Python/Qt and the retro font, but still require native mpv installed on the host. They are **not** notarized installers, Flatpaks, or AppImages. Build on each target platform/architecture; PyInstaller does not cross-compile.

Normal CI builds wheel/sdist artifacts for every matrix entry. Main-branch pushes and manual runs of the Desktop compatibility workflow also build unsigned desktop bundles for Linux and macOS and smoke-test their launchers. Do not publish an unsigned bundle as a signed Mac release.

## Release gates

- Signing and notarization need an Apple Developer identity, team ID and notarization credentials. None are stored in this repository. Do not disable Gatekeeper to test a release.
- Test on Intel and Apple Silicon Macs and on Linux X11 and Wayland with real graphics/audio devices before claiming coverage of those hardware combinations.
- A Flatpak/AppImage with bundled mpv requires a separate distribution integration and codec/runtime license review. The initial desktop bundle deliberately uses the native installed player.
- `questionbox/` remains unchanged; this release does not deploy its server or firmware.

## Manual graphical acceptance

Use short synthetic videos rather than personal libraries for repeatable acceptance.

1. Start with `nostalgiabox --desktop -c /tmp/tv-first-run.yaml`. Choose a library with two show subfolders. Review channels and Watch. Verify that no YAML edit or account is required.
2. Press G. Up/down moves the highlighted row while the show keeps playing. Enter tunes; Escape closes the guide without quitting. With the guide closed, Q quits and Escape also quits. F toggles fullscreen.
3. Press I and inspect the episode banner above the subtitle area. Check Modern, CRT, large text, high contrast, and reduced motion in Settings → Watching.
4. Press S. Preview a different appearance, then Cancel: the show must keep its position and restore its saved appearance. Save changes and confirm playback continues. Restart and verify persistence.
5. In Channels, edit numbers/names/order/exclusions. A duplicate number or missing folder must show an inline error without replacing the saved config. Add a new discovered show that alphabetically precedes existing shows; existing numbers must stay stable.
6. Disconnect the library drive. A recoverable error must appear; reconnect and allow the background scan to recover. Try a corrupt video: retries must back off rather than rapidly spin through the library.
7. Rapidly change channels near EOF. An outgoing file's completion must not advance the new channel. Check native fullscreen, speaker output/mute, hardware decode, and close-window cleanup.

Automated tests cover the forms offscreen, atomic persistence, cancellation, metadata invalidation, guide actions, event generations, and real native mpv IPC. Offscreen form tests and null-output playback tests do not prove all physical graphics/audio combinations.
