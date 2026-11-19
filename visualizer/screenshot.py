"""On-demand, bounded window capture for the current live game."""
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
INTERVAL = 2
MAX_BYTES = 512 * 1024


def client_crop(frame_size, client, bounds):
    """Find the capture origin from the bounds that match its pixel dimensions."""
    width, height = frame_size
    for x, y, right, bottom in bounds:
        if (right - x, bottom - y) != frame_size:
            continue
        left, top, edge, base = client
        if x <= left < edge <= x + width and y <= top < base <= y + height:
            return left - x, top - y, edge - x, base - y
    return None


def capture_window(pid, observed_at):
    """Run only in the disposable capture process."""
    import ctypes
    from ctypes import wintypes

    import psutil

    process = psutil.Process(pid)
    exe = Path(process.exe()).resolve()
    if (exe.name.lower() != 'zombies-arent-real.exe'
            or exe.parent.parent != ROOT.parent / 'game-copies'
            or not re.fullmatch(r'inst[0-9]+', exe.parent.name)
            or process.create_time() > observed_at):
        raise ValueError('Expected a live, repository-owned game')

    sys.path.insert(0, str(ROOT / 'runtime' / 'screenshot-deps'))
    sys.path.insert(0, str(ROOT.parent / 'scripts'))
    import cv2
    from windows_capture import WindowsCapture
    from zar_input import window_of_pid

    hwnd = window_of_pid(pid)
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    handle = wintypes.HWND(hwnd)

    def available():
        owner = wintypes.DWORD()
        return (user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
                and owner.value == pid and not user32.IsIconic(handle) and process.is_running())

    if not available():
        return
    cv2.setNumThreads(1)
    capture = WindowsCapture(window_hwnd=hwnd, cursor_capture=False, secondary_window=False)

    def crop(frame):
        rect, origin = wintypes.RECT(), wintypes.POINT()
        if not (user32.GetClientRect(handle, ctypes.byref(rect))
                and user32.ClientToScreen(handle, ctypes.byref(origin))):
            return None
        client = (origin.x, origin.y, origin.x + rect.right, origin.y + rect.bottom)
        bounds = []
        visible = wintypes.RECT()
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(
                handle, 9, ctypes.byref(visible), ctypes.sizeof(visible)) == 0:  # DWMWA_EXTENDED_FRAME_BOUNDS
            bounds.append((visible.left, visible.top, visible.right, visible.bottom))
        window = wintypes.RECT()
        if user32.GetWindowRect(handle, ctypes.byref(window)):
            bounds.append((window.left, window.top, window.right, window.bottom))
        return client_crop((frame.width, frame.height), client, bounds)

    @capture.event
    def on_frame_arrived(frame, control):
        captured_at = time.time()
        try:
            rect = crop(frame) if available() else None
            if rect is None:
                return
            left, top, right, bottom = rect
            pixels = frame.frame_buffer[top:bottom, left:right, :3]
            height, width = pixels.shape[:2]
            scale = min(1, 1280 / width, 960 / height)
            size = (max(1, round(width * scale)), max(1, round(height * scale)))
            if scale < 1:
                pixels = cv2.resize(pixels, size, interpolation=cv2.INTER_AREA)
            ok, image = cv2.imencode('.jpg', pixels, [
                cv2.IMWRITE_JPEG_QUALITY, 88,
                cv2.IMWRITE_JPEG_SAMPLING_FACTOR, cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444,
            ])
            if ok and image.nbytes > MAX_BYTES:
                ok, image = cv2.imencode('.jpg', pixels, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok and image.nbytes <= MAX_BYTES and available():
                sys.stdout.buffer.write(struct.pack('!d', captured_at) + image.tobytes())
                sys.stdout.buffer.flush()
        finally:
            control.stop()

    @capture.event
    def on_closed():
        pass

    capture.start()


class Screenshots:
    """At most one capture subprocess and one cached frame across all viewers."""

    def __init__(self):
        self.lock = threading.Lock()
        self.last_request = float('-inf')
        self.pending = False
        self.cached = None

    def __call__(self, stream, pid, observed_at):
        key = (stream, pid)
        with self.lock:
            now = time.monotonic()
            if not self.pending and now - self.last_request >= INTERVAL:
                self.pending = True
                self.last_request = now
                threading.Thread(target=self._capture, args=(key, observed_at), daemon=True).start()
            if self.cached and self.cached[0] == key and time.time() - self.cached[1] <= 6:
                return self.cached[1:]
        return None

    def _capture(self, key, observed_at):
        try:
            output = subprocess.run(
                [sys.executable, '-B', str(Path(__file__).resolve()), str(key[1]), str(observed_at)],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=4, check=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            ).stdout
            if 12 <= len(output) <= MAX_BYTES + 8 and output[8:10] == b'\xff\xd8' and output[-2:] == b'\xff\xd9':
                stamp, = struct.unpack_from('!d', output)
                if math.isfinite(stamp) and 0 <= time.time() - stamp <= 6:
                    with self.lock:
                        self.cached = (key, stamp, output[8:])
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            with self.lock:
                self.pending = False


if __name__ == '__main__':
    # The helper also exits on its own if the observatory stops mid-capture.
    deadline = threading.Timer(3.5, os._exit, args=(1,))
    deadline.daemon = True
    deadline.start()
    try:
        capture_window(int(sys.argv[1]), float(sys.argv[2]))
    finally:
        deadline.cancel()
