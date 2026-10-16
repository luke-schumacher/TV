# TV implementation plan

## Delivery and acceptance

1. **First run and watching:** a Qt library picker and channel review when desktop config is missing/unreadable; G guide with selection and Enter to tune, Escape to return; episode banner; a dismissible help hint. Validate setup without YAML and guide navigation with synthetic media.
2. **Settings:** a modeless native Qt control panel, library/channel forms, advanced exclusions, audio devices, Modern/CRT preview, font scaling, high contrast, reduced motion. Validate a draft before atomic save; preserve unknown YAML keys; Cancel restores the preview and keeps the show playing.
3. **Reliability:** explicit platform profiles and player capabilities, immutable viewing snapshots, stale-event rejection, playback error backoff, cancellable background scans, persistent duration cache, stable discovered channel numbers, versioned configuration/bookmark migrations. Validate corrupt/missing libraries and rapid channel changes.
4. **Distribution:** versioned wheel/sdist artifacts, optional standalone Qt desktop bundles, Linux/macOS CI including GUI tests with an offscreen renderer and native mpv integration. Add manual graphical acceptance instructions. Apple signing/notarization and physical Intel/ARM/Wayland/X11 hardware acceptance require credentials/hardware unavailable to this checkout; keep those release gates explicit.

## Architecture decision

Keep mpv as a native child process for desktop playback and ASS for the guide. Qt runs the application timer and modeless setup/settings window on the main thread, while scanning/probing happens in bounded background workers. Do not migrate to embedded rendering until a separate Cocoa/Wayland render API prototype has passed acceptance. Pi users retain the existing service, libmpv, evdev and CEC path. Keep questionbox untouched.

## Verification

Run the existing suite, focused state/IPC/persistence and Qt tests, a built-wheel font check, and the Ubuntu/macOS CI matrix. Exercise setup, settings cancellation/save, guide, fullscreen, volume, EOF and close with generated media. Document actual results and remaining release gates in this file before delivery.

## Implementation record (16 October 2026)

- Implemented stages 1–3 for the native desktop path: setup/recovery, ASS channel guide, episode banner/help, modeless settings and preview/cancel, accessibility options, capabilities/profile policy, immutable snapshots, generation-tagged native playback events, retry backoff, background reconciliation/probe cache, stable discovery numbering, atomic schema-aware persistence with legacy backups.
- Stage 4: version 1.1.0 wheel and sdist built; unsigned ARM64 macOS Qt app ZIP built and launched with generated media. The standalone app accepted guide input and exited cleanly. CI builds downloadable Python artifacts; a manual workflow additionally builds unsigned native Linux/macOS bundles.
- Local verification: 173 tests pass on macOS/Python 3.9, including Qt form flows and native mpv IPC. End-to-end generated-media check covers guide/tune, preview cancellation, save without restarting playback, and native bundle startup/exit. Setup and settings forms were rendered and visually inspected.
- Background discovery benchmark: 10,000 synthetic empty episode files scanned and statted in 0.217 seconds on this machine. This excludes decoding, cold storage and real-media duration probing; it is a baseline rather than a hardware-wide performance claim.
- Release gates remain: Apple signing/notarization credentials, physical Intel/ARM/X11/Wayland graphics/audio checks, and optional embedded rendering or Flatpak/AppImage integration. The tested native-process player remains the desktop renderer. Pi hardware behavior is preserved; generation IDs apply to the native IPC adapter rather than pretending libmpv exposes equivalent event identity.
