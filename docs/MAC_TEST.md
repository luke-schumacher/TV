# First visible Mac test — 16 October 2026

Tested the locally built TV.app on this Apple Silicon Mac with its native Cocoa settings window and native mpv video window. Used the generated offline demo library, separate from the normal user configuration.

Passed:

- Three cached synthetic channels generated with quiet audio; playback repeats at episode end.
- Native settings: channel review lists all three channels; appearance preview and Cancel work while the show continues.
- mpv reports VideoToolbox hardware decode at 960×540 and an active 48 kHz mono audio output. This verifies the audio pipeline; perceived speaker/headphone sound still needs the user's listening check.
- Guide browsing leaves playback running; Enter tunes to Motion Lab.
- Mute/unmute and fullscreen entry/exit work. Allow the macOS fullscreen animation to finish before toggling again.
- SIGTERM cleanly exits the Qt event loop and closes its mpv child.
- Full local suite: 175 tests pass, including demo caching/failure cleanup.

The visible demo was left running for user testing. Start it again with `nostalgiabox --demo` (or `TV.app/Contents/MacOS/TV --demo`). Focus the video window: G guide, S settings, F fullscreen, arrows for channels/volume, Q quit.

Next useful UI work after this acceptance pass: subtitle/audio-track selection and a searchable guide for larger libraries. Signed distribution and physical Intel/Linux display checks remain the release gates documented in RELEASE.md.
