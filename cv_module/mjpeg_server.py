"""
Lightweight MJPEG HTTP server so the React dashboard can show the live webcam.

  GET http://127.0.0.1:8081/stream   — multipart JPEG stream
  GET http://127.0.0.1:8081/health  — {"ok": true}
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

import cv2
import numpy as np


class FrameBuffer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jpeg: Optional[bytes] = None

    def update(self, bgr_frame: np.ndarray, quality: int = 70) -> None:
        ok, buf = cv2.imencode(
            '.jpg',
            bgr_frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), quality],
        )
        if not ok:
            return
        with self._lock:
            self._jpeg = buf.tobytes()

    def get_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg


def make_handler(buffer: FrameBuffer):
    class MJPEGHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            # Keep scanner console clean
            return

        def _cors(self) -> None:
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith('/health'):
                body = b'{"ok":true}'
                self.send_response(200)
                self._cors()
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if not self.path.startswith('/stream'):
                self.send_response(404)
                self._cors()
                self.end_headers()
                return

            self.send_response(200)
            self._cors()
            self.send_header(
                'Content-Type',
                'multipart/x-mixed-replace; boundary=frame',
            )
            self.end_headers()

            try:
                while True:
                    jpeg = buffer.get_jpeg()
                    if jpeg is None:
                        time.sleep(0.05)
                        continue
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                    self.wfile.write(f'Content-Length: {len(jpeg)}\r\n\r\n'.encode())
                    self.wfile.write(jpeg)
                    self.wfile.write(b'\r\n')
                    time.sleep(0.05)  # ~20 FPS max to clients
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

    return MJPEGHandler


def start_mjpeg_server(
    buffer: FrameBuffer,
    host: str = '0.0.0.0',
    port: int = 8081,
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(buffer))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f'[STREAM] MJPEG live at http://127.0.0.1:{port}/stream')
    return server
