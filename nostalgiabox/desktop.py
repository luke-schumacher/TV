"""Desktop playback through mpv's public JSON IPC protocol.

Running the native executable gives macOS its own Cocoa event loop and avoids
loading Homebrew's libmpv into Python. No global keyboard capture is needed.
"""
from __future__ import annotations

import json
import queue
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .actions import Action, InputEvent
from .input.keymap import evdev_key_to_event
from .player import Player, END_EOF, END_ERROR

WINDOW_KEYS = {
    "UP": "KEY_UP", "DOWN": "KEY_DOWN", "LEFT": "KEY_LEFT", "RIGHT": "KEY_RIGHT",
    "PGUP": "KEY_PAGEUP", "PGDWN": "KEY_PAGEDOWN", "+": "KEY_VOLUMEUP",
    "=": "KEY_VOLUMEUP", "-": "KEY_VOLUMEDOWN", "m": "KEY_M", "i": "KEY_I",
    "l": "KEY_L", "p": "KEY_P", "q": "KEY_Q", "ESC": "KEY_ESC",
    "ENTER": "KEY_ENTER", **{str(n): f"KEY_{n}" for n in range(10)},
}


class DesktopPlayer(Player):
    """Own one native mpv process, socket, reader thread, and temporary directory."""

    def __init__(self, *, fullscreen=False, force_4_3=False, audio_device=None,
                 glsl_shaders=None, fonts_dir=None):
        binary = shutil.which("mpv")
        if not binary:
            raise RuntimeError("mpv is missing. macOS: brew install mpv; Ubuntu/Debian: sudo apt install mpv")
        self._temp = tempfile.TemporaryDirectory(prefix="tv-")
        root = Path(self._temp.name)
        ipc = root / "ipc"
        bindings = root / "input.conf"
        bindings.write_text("\n".join(
            f"{key} script-message tv-key {value}" for key, value in WINDOW_KEYS.items()
        ) + "\nf cycle fullscreen\nCLOSE_WIN script-message tv-quit\n")
        args = [binary, "--no-config", "--idle=yes", "--force-window=yes",
                "--keep-open=yes", "--input-default-bindings=no", "--input-terminal=no",
                "--osc=no", "--terminal=no", "--input-vo-keyboard=yes", "--volume-max=100", "--replaygain=no", "--hwdec=auto-safe",
                f"--input-ipc-server={ipc}", f"--input-conf={bindings}",
                f"--fullscreen={'yes' if fullscreen else 'no'}", "--title=TV"]
        if audio_device:
            args.append(f"--audio-device={audio_device}")
        if glsl_shaders:
            args.append(f"--glsl-shaders={glsl_shaders}")
        if fonts_dir:
            args.append(f"--osd-fonts-dir={fonts_dir}")
        if force_4_3:
            args.append("--vf=lavfi=[scale=960:720:force_original_aspect_ratio=decrease,pad=960:720:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1]")
        self._closed = False
        self._suppress = True
        self._pending = None
        self.on_input = None
        self._events = queue.Queue()
        self._responses = {}
        self._lock = threading.Lock()
        self._serial = 0
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._process = None
        try:
            self._process = subprocess.Popen(args)
            deadline = time.monotonic() + 10
            while True:
                try:
                    self._sock.connect(str(ipc))
                    break
                except (FileNotFoundError, ConnectionRefusedError):
                    if self._process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("mpv could not open a desktop window. Check your display and mpv installation.")
                    time.sleep(0.05)
            self._reader = threading.Thread(target=self._read, daemon=True, name="tv-mpv")
            self._reader.start()
            self._command("observe_property", 1, "eof-reached")
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            with self._sock.makefile("rb") as stream:
                for line in stream:
                    event = json.loads(line)
                    if "request_id" in event:
                        with self._lock:
                            response = self._responses.get(event["request_id"])
                        if response is not None:
                            response.put(event)
                    else:
                        self._events.put(event)
        except (OSError, ValueError):
            pass
        finally:
            self._events.put({"event": "shutdown"})

    def poll_events(self):
        """Dispatch on the app thread, keeping IPC reads free to receive replies."""
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return
            kind = event.get("event")
            if kind == "client-message":
                args = event.get("args", [])
                if args and args[0] == "tv-key" and len(args) > 1:
                    action = evdev_key_to_event(args[1])
                    if action and self.on_input:
                        self.on_input(action)
                elif args and args[0] == "tv-quit" and self.on_input:
                    self.on_input(InputEvent(Action.QUIT))
            elif kind == "shutdown" and self.on_input:
                self.on_input(InputEvent(Action.QUIT))
            elif not self._suppress and self.on_end:
                if kind == "property-change" and event.get("name") == "eof-reached" and event.get("data"):
                    self.on_end(END_EOF)
                elif kind == "end-file" and event.get("reason") == "error":
                    self.on_end(END_ERROR)

    def _command(self, *args):
        if self._closed:
            return None
        response = queue.Queue()
        with self._lock:
            self._serial += 1
            serial = self._serial
            self._responses[serial] = response
            try:
                self._sock.sendall((json.dumps({"command": args, "request_id": serial}) + "\n").encode())
            except OSError:
                self._responses.pop(serial, None)
                return None
        try:
            result = response.get(timeout=2)
            if result.get("error") != "success":
                import logging
                logging.getLogger(__name__).warning("mpv %s: %s", args[0], result.get("error"))
            return result.get("data")
        except queue.Empty:
            return None
        finally:
            with self._lock:
                self._responses.pop(serial, None)

    def play(self, path, *, start=0.0):
        self._suppress = False
        self._command("set_property", "loop-file", "no")
        # Set start as a property to support both pre-0.38 and current loadfile APIs.
        self._command("set_property", "start", str(max(0, start)))
        self._command("loadfile", str(path), "replace")
        self._command("set_property", "pause", False)

    def play_loop(self, path):
        self.play(path)
        self._suppress = True
        self._command("set_property", "loop-file", "inf")

    def preload_next(self, target_path, *, start=0.0):
        self._pending = (target_path, start)

    def commit_switch(self):
        if self._pending:
            path, start = self._pending
            self._pending = None
            self.play(path, start=start)

    def stop(self):
        self._suppress = True
        self._pending = None
        self._command("stop")

    def set_volume(self, volume):
        self._command("set_property", "volume", max(0, min(100, int(volume))))

    def set_mute(self, muted):
        self._command("set_property", "mute", bool(muted))

    def get_time_pos(self):
        return self._command("get_property", "time-pos")

    def show_text(self, text, duration):
        self._command("show-text", text, int(duration * 1000))

    def set_overlay(self, overlay_id, ass, res_x, res_y):
        self._command("osd-overlay", overlay_id, "ass-events", ass, res_x, res_y)

    def clear_overlay(self, overlay_id):
        self._command("osd-overlay", overlay_id, "none", "")

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._sock.close()
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        if hasattr(self, "_reader"):
            self._reader.join(timeout=2)
        self._temp.cleanup()
