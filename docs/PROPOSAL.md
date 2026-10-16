# TV: UI and architecture proposal

These are proposed follow-up changes, separate from the desktop compatibility implementation. Preserve the immediate, remote-friendly viewing experience: launching TV should put a show on screen, with library management available on demand.

## Priority 1 — Make setup visible and recoverable

Replace the empty-library wait loop on desktops with a setup screen: **Choose library → Review channels → Watch**. A folder picker should persist an absolute path, show read errors inline, and explain the one-folder-per-show model. Keep the CLI report for headless/Pi use. Do not require sign-in or a server.

Add a compact channel guide on a dedicated key (G): number, show name, current episode, and progress. Up/down selects, Enter tunes, Escape returns to the current show. Preserve immediate up/down channel surfing outside the guide. Use a clear selection ring, large targets, and text labels; never make green alone carry state.

Provide a short, dismissible first-run hint: “↑↓ channels · ←→ volume · G guide · F fullscreen”. An I banner should show the episode title as well as the channel and should avoid covering subtitles. Add a Modern/CRT appearance switch, readable font scaling, high contrast, and a reduced-motion setting that disables glitch/static and curvature animations.

Acceptance: a new user can select a library, tune a channel, and quit without editing YAML; a missing drive produces a recoverable state; every guide action works with a keyboard/Flirc remote.

## Priority 2 — Separate settings from watching

Put library roots, channel names/numbers, shuffle/order/resume options, exclusions, audio output, and appearance into a settings panel. Save atomically, validate before applying, and expose the same schema to CLI and UI. Allow previewing the CRT effect before saving. Keep viewing state when settings close.

Use progressive disclosure: a few everyday settings first; per-channel exclusions and advanced hardware controls behind an Advanced section. On desktops, power means standby in TV; host shutdown belongs exclusively in an explicit appliance profile. Show the active playback and volume mode in diagnostics.

Acceptance: settings round-trip existing YAML without discarding unknown extension keys; invalid paths or duplicate channel numbers cannot overwrite a working configuration; cancellation leaves playback intact.

## Architecture

The current `Player` boundary and action queue are useful and should remain. The port adds a native mpv process adapter because it gives macOS a proper window event loop and keeps desktop input within the window. The Pi's libmpv/evdev/CEC adapter remains available.

| Boundary | Owns | Change |
| --- | --- | --- |
| Domain | Channel lineup, ordering, broadcast clock, bookmarks | Keep Python, free of OS and UI dependencies |
| Application | Actions, playback transitions, standby, error recovery | Explicit state machine and immutable view snapshot |
| Player adapter | mpv commands/events, rendering, position | Formal capabilities for preloading, transitions, overlays, fullscreen |
| Platform profile | Paths, inputs, volume routing, shutdown | Explicit desktop/appliance profiles resolved once at startup |
| Library service | Discovery, metadata, duration probes | Background scan with cancellation and an mtime/size cache |
| Presentation | Viewing banner, guide, settings | Consume actions and snapshots; never call OS shutdown or scan recursively |

A formal capability record prevents the current desktop adapter's immediate transition fallback from pretending to offer Pi-style preloading. Choose the transition strategy before tuning. Add a generation ID to playback events so an EOF/error from an outgoing file cannot advance the newly selected channel. Keep callbacks on a queue and execute application actions on one thread.

Move ffprobe work out of startup and channel switches. Cache duration by resolved path, size, and modification time; use a bounded worker pool. Reconcile libraries incrementally when drives mount or files change. Stable channel IDs should use saved identity rather than discovery order, so adding a show does not renumber all favorites or break bookmarks.

Persist config and playback state using temporary files and atomic rename. Version both schemas; migrate old versions with backups. Distinguish missing files, unsupported codecs, and failed video output in user-visible errors, and back off after repeated failures instead of spinning through a broken library.

## Presentation technology decision

For an initial guide, extend the existing ASS overlay renderer: few dependencies, remote friendly, and consistent with the current player. A real settings form and folder picker will eventually exceed ASS's strengths. At that point, use a small native Qt shell around the same domain/actions and embed mpv via its supported render API. Prototype macOS rendering and Linux Wayland before committing to that migration.

Avoid adding Electron or a mandatory local web server simply for settings. A browser-based companion could be optional later if remote administration becomes a real requirement. Its API would need authentication and explicit network binding; it should not expand the scope of this desktop port.

## Repository and packaging

Keep the `nostalgiabox` import/package name during the compatibility phase so old configs and service scripts survive. Use TV in user-facing copy. A later release can add a carefully chosen launcher name after checking PATH collisions (`tv` already names unrelated tools). Split or archive `questionbox/` into its own repository in a separately approved change; it is an independent ESP32/AI product with different dependencies and release cycles.

Ship versioned wheels first. Follow with a signed/notarized Mac app and a Linux Flatpak or AppImage only after the graphical smoke matrix is reliable. Record mpv versions, test Intel and Apple Silicon Macs, and test both Wayland and X11. Packaging must preserve the bundled OFL font and license.

## Suggested delivery order

1. **Compatibility baseline (this change):** native desktop process, focused-window controls, safe volume behavior, setup docs, packaged fonts, macOS/Linux CI and real IPC smoke test.
2. **First-run and guide:** library picker/empty state, guide navigation, episode banner, accessibility settings. Validate with a keyboard and a basic remote.
3. **Reliability:** capability negotiation, transition generation IDs, async scan/cache, corrupt-file recovery, stable channel identity, state migration tests.
4. **Settings and distribution:** settings UI prototype and technology decision, packaged desktop apps, native graphical acceptance checks.

Success measures: time from launch to first frame, channel-switch latency (median and 95th percentile), first-run completion without YAML, startup cost on a 10,000-file library, and zero accidental host shutdowns in desktop mode. Set numeric performance budgets after measuring the current player on representative hardware.

## References

- [mpv manual: JSON IPC and input bindings](https://mpv.io/manual/stable/) — public protocol used by the desktop adapter.
- [python-mpv platform notes](https://github.com/jaseg/python-mpv#supported-platforms) — macOS event-loop concerns motivating a native process.
- [Upstream NostalgiaBox](https://github.com/landonbtw/NostalgiaBox) — original implementation and MIT attribution.
