#!/usr/bin/env python3
"""
Smart Gate — Real-time webcam plate scanner (OpenCV + EasyOCR)

By default the scanner continuously watches the green ROI and, when a plate
is stably detected, POSTs to Django /api/scan/ automatically (entry or exit).

Controls
--------
  s  — force an immediate scan (ignores confirm streak)
  a  — toggle auto-scan on/off
  c  — cycle camera_type: auto → entry → exit → auto
  q  — quit

Usage
-----
  python scanner.py
  python scanner.py --type auto --api http://127.0.0.1:8000
  python scanner.py --type entry --camera 0          # entry lane
  python scanner.py --type exit  --camera 1          # exit lane
  python scanner.py --no-auto                        # manual S only
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import cv2
import easyocr
import numpy as np
import requests

from api_client import post_scan
from config import (
    API_BASE_URL,
    AUTO_SCAN_ENABLED,
    AUTO_SCAN_INTERVAL,
    CAMERA_INDEX,
    CAMERA_TYPE,
    CONFIRM_READS,
    MIN_OCR_CONFIDENCE,
    OCR_GPU,
    OCR_LANGUAGES,
    PLATE_COOLDOWN_SECONDS,
    STREAM_ENABLED,
    STREAM_HOST,
    STREAM_PORT,
    WINDOW_NAME,
)
from mjpeg_server import FrameBuffer, start_mjpeg_server
from plate_utils import extract_best_plate

CAMERA_TYPES = ("auto", "entry", "exit")
PLATE_ALLOWLIST = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ "


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Gate real-time CV scanner")
    parser.add_argument("--camera", default=str(CAMERA_INDEX))
    parser.add_argument("--type", choices=CAMERA_TYPES, default=CAMERA_TYPE)
    parser.add_argument("--api", default=API_BASE_URL)
    parser.add_argument("--gpu", action="store_true", default=OCR_GPU)
    parser.add_argument("--min-conf", type=float, default=MIN_OCR_CONFIDENCE)
    parser.add_argument(
        "--interval",
        type=float,
        default=AUTO_SCAN_INTERVAL,
        help="Seconds between automatic OCR attempts",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=PLATE_COOLDOWN_SECONDS,
        help="Seconds before the same plate can be posted again",
    )
    parser.add_argument(
        "--confirm",
        type=int,
        default=CONFIRM_READS,
        help="Identical consecutive OCR hits required before POST",
    )
    parser.add_argument(
        "--no-auto",
        action="store_true",
        help="Disable continuous auto-scan (manual S only)",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable MJPEG dashboard stream server",
    )
    parser.add_argument(
        "--stream-port",
        type=int,
        default=STREAM_PORT,
        help="MJPEG stream port (default 8081)",
    )
    return parser.parse_args()


def gui_available() -> bool:
    try:
        probe = np.zeros((40, 40, 3), dtype=np.uint8)
        cv2.imshow("__smart_gate_probe__", probe)
        cv2.waitKey(1)
        cv2.destroyWindow("__smart_gate_probe__")
        return True
    except cv2.error:
        return False


def open_capture(source: str) -> cv2.VideoCapture:
    cam: int | str = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(cam)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera/source: {source}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return cap


def roi_box(frame: np.ndarray) -> tuple[int, int, int, int]:
    h, w = frame.shape[:2]
    margin_x, margin_y = int(w * 0.18), int(h * 0.32)
    return margin_x, margin_y, w - margin_x, h - margin_y


def preprocess_for_ocr(bgr: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    scale = 2.0 if max(h, w) < 900 else 1.5
    up = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(up, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)


def run_ocr(
    reader: easyocr.Reader,
    frame: np.ndarray,
    min_conf: float,
    *,
    roi_only: bool = True,
) -> tuple[str | None, list[dict[str, Any]]]:
    x1, y1, x2, y2 = roi_box(frame)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        crop = frame

    images = [preprocess_for_ocr(crop)]
    if not roi_only:
        images.append(preprocess_for_ocr(frame))

    texts: list[str] = []
    hits: list[dict[str, Any]] = []

    for img in images:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = reader.readtext(
            rgb,
            allowlist=PLATE_ALLOWLIST,
            detail=1,
            paragraph=False,
        )
        for _bbox, text, conf in results:
            if conf < min_conf:
                continue
            texts.append(text)
            hits.append({"text": text, "confidence": float(conf)})

        plate = extract_best_plate(texts)
        if plate:
            return plate, hits

    return extract_best_plate(texts), hits


def draw_overlay(
    frame: np.ndarray,
    *,
    camera_type: str,
    status_line: str,
    last_plate: str | None,
    last_action: str | None,
    auto_on: bool,
) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]
    mode = "AUTO" if auto_on else "MANUAL"

    cv2.rectangle(out, (0, 0), (w, 78), (15, 23, 42), -1)
    cv2.putText(
        out,
        f"Smart Gate CV [{mode}]  |  [S] force  [A] auto  [C] type  [Q] quit",
        (16, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (204, 251, 241),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        out,
        f"type={camera_type}   plate={last_plate or '-'}   action={last_action or '-'}",
        (16, 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (226, 232, 240),
        1,
        cv2.LINE_AA,
    )

    cv2.rectangle(out, (0, h - 40), (w, h), (15, 23, 42), -1)
    cv2.putText(
        out,
        status_line[:110],
        (16, h - 14),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (148, 163, 184),
        1,
        cv2.LINE_AA,
    )

    x1, y1, x2, y2 = roi_box(out)
    color = (45, 212, 191) if auto_on else (148, 163, 184)
    cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
    cv2.putText(
        out,
        "PLACE PLATE HERE",
        (x1 + 8, y1 + 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        1,
        cv2.LINE_AA,
    )
    return out


def cycle_camera_type(current: str) -> str:
    idx = CAMERA_TYPES.index(current) if current in CAMERA_TYPES else 0
    return CAMERA_TYPES[(idx + 1) % len(CAMERA_TYPES)]


def post_plate(
    plate: str,
    *,
    camera_type: str,
    scan_url: str,
) -> tuple[str, str, dict[str, Any] | None]:
    """Returns (status_line, action, raw_data_or_none)."""
    try:
        data = post_scan(plate, camera_type=camera_type, endpoint=scan_url)
        action = str(data.get("action", "?"))
        direction = str(data.get("direction", camera_type))
        line = f"{plate} → {action} ({direction})"
        print(f"[API] {line}  raw={data}")
        return line, action, data
    except requests.RequestException as exc:
        line = f"API error: {exc}"
        print(line)
        return line, "error", None


def main() -> int:
    args = parse_args()
    scan_url = f"{args.api.rstrip('/')}/api/scan/"
    auto_on = AUTO_SCAN_ENABLED and not args.no_auto

    print("=" * 60)
    print("Smart Gate CV Scanner (real-time)")
    print(f"  camera   : {args.camera}")
    print(f"  type     : {args.type}")
    print(f"  API      : {scan_url}")
    print(f"  auto     : {auto_on}")
    print(f"  interval : {args.interval}s")
    print(f"  cooldown : {args.cooldown}s")
    print(f"  confirm  : {args.confirm} reads")
    stream_on = STREAM_ENABLED and not args.no_stream
    print(f"  stream   : {'on' if stream_on else 'off'} (:{args.stream_port})")
    print("=" * 60)
    print("Loading EasyOCR model...")

    if not gui_available():
        print(
            "ERROR: OpenCV GUI unavailable. Fix:\n"
            "  pip uninstall -y opencv-python-headless\n"
            "  pip install --force-reinstall opencv-python"
        )
        return 1

    reader = easyocr.Reader(OCR_LANGUAGES, gpu=args.gpu)
    cap = open_capture(str(args.camera))

    frame_buffer = FrameBuffer()
    if stream_on:
        start_mjpeg_server(frame_buffer, host=STREAM_HOST, port=args.stream_port)

    camera_type = args.type
    last_plate: str | None = None
    last_action: str | None = None
    status_line = (
        "AUTO: place plate in green box"
        if auto_on
        else "MANUAL: press S to scan"
    )

    last_ocr_at = 0.0
    plate_cooldown: dict[str, float] = {}
    pending_plate: str | None = None
    pending_count = 0
    busy = False

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                status_line = "Camera read failed"
                time.sleep(0.05)
                continue

            # Publish annotated preview to dashboard MJPEG clients
            preview = draw_overlay(
                frame,
                camera_type=camera_type,
                status_line=status_line,
                last_plate=last_plate,
                last_action=last_action,
                auto_on=auto_on,
            )
            if stream_on:
                frame_buffer.update(preview)

            now = time.time()
            display = preview
            cv2.imshow(WINDOW_NAME, display)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break

            if key == ord("c"):
                camera_type = cycle_camera_type(camera_type)
                status_line = f"Camera type → {camera_type}"
                print(status_line)
                continue

            if key == ord("a"):
                auto_on = not auto_on
                status_line = f"Auto-scan {'ON' if auto_on else 'OFF'}"
                print(status_line)
                continue

            force = key == ord("s")
            due = auto_on and (now - last_ocr_at) >= args.interval

            if busy or (not force and not due):
                continue

            busy = True
            last_ocr_at = now
            status_line = "OCR scanning..."
            scanning_preview = draw_overlay(
                frame,
                camera_type=camera_type,
                status_line=status_line,
                last_plate=last_plate,
                last_action=last_action,
                auto_on=auto_on,
            )
            if stream_on:
                frame_buffer.update(scanning_preview)
            cv2.imshow(WINDOW_NAME, scanning_preview)
            cv2.waitKey(1)

            plate, hits = run_ocr(
                reader,
                frame,
                args.min_conf,
                roi_only=not force,
            )
            print(f"[OCR] hits={len(hits)} plate={plate!r}")
            for hit in hits[:6]:
                print(f"       conf={hit['confidence']:.2f} text={hit['text']!r}")

            if not plate:
                pending_plate = None
                pending_count = 0
                status_line = "Watching… (no plate in ROI)"
                busy = False
                continue

            cooled_until = plate_cooldown.get(plate, 0.0)
            if not force and now < cooled_until:
                remaining = int(cooled_until - now)
                status_line = f"{plate} on cooldown ({remaining}s)"
                busy = False
                continue

            if force:
                # Manual force: post immediately
                confirm_ok = True
                pending_plate = None
                pending_count = 0
            else:
                if plate == pending_plate:
                    pending_count += 1
                else:
                    pending_plate = plate
                    pending_count = 1
                confirm_ok = pending_count >= max(1, args.confirm)
                status_line = f"Seen {plate} ({pending_count}/{args.confirm})"

            if not confirm_ok:
                busy = False
                continue

            last_plate = plate
            status_line = f"Posting {plate}..."
            line, action, _data = post_plate(
                plate,
                camera_type=camera_type,
                scan_url=scan_url,
            )
            last_action = action
            status_line = line
            plate_cooldown[plate] = now + args.cooldown
            pending_plate = None
            pending_count = 0
            busy = False

    finally:
        cap.release()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass

    print("Scanner stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
