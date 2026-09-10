#!/usr/bin/env python3
"""
Smart Gate — Real-time webcam plate scanner (OpenCV + EasyOCR)

Road-camera style (default): motion in the green ROI triggers OCR once per
vehicle passage, then waits until the lane clears. No continuous OCR spam.

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
  python scanner.py --trigger motion          # default: ANPR-style
  python scanner.py --trigger interval        # legacy timed OCR
  python scanner.py --type entry --camera 0
  python scanner.py --no-auto                 # manual S only
"""

from __future__ import annotations

import argparse
import sys
import threading
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
    MAX_OCR_PER_PASSAGE,
    MIN_OCR_CONFIDENCE,
    MOTION_CLEAR_FRAMES,
    MOTION_DIFF_THRESHOLD,
    MOTION_MIN_CHANGE,
    MOTION_SETTLE_SECONDS,
    OCR_GPU,
    OCR_LANGUAGES,
    PLATE_COOLDOWN_SECONDS,
    ROI_MIN_EDGE_RATIO,
    STREAM_ENABLED,
    STREAM_HOST,
    STREAM_PORT,
    TRIGGER_MODE,
    WINDOW_NAME,
)
from mjpeg_server import FrameBuffer, start_mjpeg_server
from motion import RoiMotionTrigger
from plate_utils import extract_best_plate

CAMERA_TYPES = ("auto", "entry", "exit")
TRIGGER_MODES = ("motion", "interval")
PLATE_ALLOWLIST = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ "


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Gate real-time CV scanner")
    parser.add_argument("--camera", default=str(CAMERA_INDEX))
    parser.add_argument("--type", choices=CAMERA_TYPES, default=CAMERA_TYPE)
    parser.add_argument("--api", default=API_BASE_URL)
    parser.add_argument("--gpu", action="store_true", default=OCR_GPU)
    parser.add_argument("--min-conf", type=float, default=MIN_OCR_CONFIDENCE)
    parser.add_argument(
        "--trigger",
        choices=TRIGGER_MODES,
        default=TRIGGER_MODE if TRIGGER_MODE in TRIGGER_MODES else "motion",
        help="motion = road ANPR (default); interval = timed OCR",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=AUTO_SCAN_INTERVAL,
        help="OCR retry / poll interval in seconds",
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
        "--settle",
        type=float,
        default=MOTION_SETTLE_SECONDS,
        help="Seconds to wait after motion before first OCR",
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


def crop_roi(frame: np.ndarray) -> np.ndarray:
    x1, y1, x2, y2 = roi_box(frame)
    return frame[y1:y2, x1:x2]


def preprocess_for_ocr(bgr: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    scale = 2.0 if max(h, w) < 900 else 1.5
    up = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(up, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)


def roi_has_content(frame: np.ndarray, min_edge_ratio: float = ROI_MIN_EDGE_RATIO) -> bool:
    """Cheap gate: skip full OCR when the green box looks empty (interval mode)."""
    crop = crop_roi(frame)
    if crop.size == 0:
        return True
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(small, 60, 140)
    return float(np.count_nonzero(edges)) / float(edges.size) >= min_edge_ratio


def run_ocr(
    reader: easyocr.Reader,
    frame: np.ndarray,
    min_conf: float,
    *,
    roi_only: bool = True,
) -> tuple[str | None, list[dict[str, Any]]]:
    crop = crop_roi(frame)
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
    trigger: str,
    motion_score: float = 0.0,
) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]
    mode = "AUTO" if auto_on else "MANUAL"

    cv2.rectangle(out, (0, 0), (w, 78), (15, 23, 42), -1)
    cv2.putText(
        out,
        f"Smart Gate CV [{mode}/{trigger}]  |  [S] force  [A] auto  [C] type  [Q] quit",
        (16, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (204, 251, 241),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        out,
        f"type={camera_type}   plate={last_plate or '-'}   action={last_action or '-'}"
        + (f"   motion={motion_score:.0%}" if trigger == "motion" else ""),
        (16, 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
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
    trigger = args.trigger

    print("=" * 60)
    print("Smart Gate CV Scanner (road-camera style)")
    print(f"  camera   : {args.camera}")
    print(f"  type     : {args.type}")
    print(f"  API      : {scan_url}")
    print(f"  auto     : {auto_on}")
    print(f"  trigger  : {trigger}")
    print(f"  interval : {args.interval}s (retry while vehicle present)")
    print(f"  cooldown : {args.cooldown}s")
    print(f"  confirm  : {args.confirm} reads")
    if trigger == "motion":
        print(f"  settle   : {args.settle}s")
        print(f"  clear    : {MOTION_CLEAR_FRAMES} frames")
        print(f"  max OCR  : {MAX_OCR_PER_PASSAGE}/passage")
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

    motion = RoiMotionTrigger(
        diff_threshold=MOTION_DIFF_THRESHOLD,
        min_change_ratio=MOTION_MIN_CHANGE,
    )

    camera_type = args.type
    last_plate: str | None = None
    last_action: str | None = None
    status_line = (
        "AUTO: waiting for vehicle in green box"
        if auto_on and trigger == "motion"
        else ("AUTO: place plate in green box" if auto_on else "MANUAL: press S to scan")
    )

    last_ocr_at = 0.0
    plate_cooldown: dict[str, float] = {}
    pending_plate: str | None = None
    pending_count = 0
    busy = False
    ocr_lock = threading.Lock()
    ocr_result: dict[str, Any] | None = None
    motion_score = 0.0

    # Motion passage state machine: idle → capturing → waiting_clear → idle
    passage_state = "idle"
    settle_until = 0.0
    ocr_attempts = 0
    vehicle_posted = False
    clear_streak = 0

    def start_ocr(frame_bgr: np.ndarray, *, force: bool) -> None:
        nonlocal busy, status_line, ocr_attempts

        def worker() -> None:
            nonlocal ocr_result, busy, last_ocr_at
            try:
                plate, hits = run_ocr(
                    reader,
                    frame_bgr,
                    args.min_conf,
                    roi_only=not force,
                )
                with ocr_lock:
                    ocr_result = {"plate": plate, "hits": hits, "force": force}
            except Exception as exc:  # noqa: BLE001 — keep UI alive
                print(f"[OCR] error: {exc}")
                with ocr_lock:
                    ocr_result = {
                        "plate": None,
                        "hits": [],
                        "force": force,
                        "error": str(exc),
                    }
            finally:
                last_ocr_at = time.time()
                busy = False

        busy = True
        if not force and trigger == "motion":
            ocr_attempts += 1
        status_line = "OCR scanning..."
        threading.Thread(target=worker, daemon=True).start()

    def handle_ocr_finished(finished: dict[str, Any]) -> None:
        nonlocal pending_plate, pending_count, last_plate, last_action
        nonlocal status_line, vehicle_posted, passage_state

        plate = finished.get("plate")
        hits = finished.get("hits") or []
        force_done = bool(finished.get("force"))
        if plate or hits:
            print(f"[OCR] hits={len(hits)} plate={plate!r}")
            for hit in hits[:6]:
                print(f"       conf={hit['confidence']:.2f} text={hit['text']!r}")

        now = time.time()
        if not plate:
            pending_plate = None
            pending_count = 0
            if trigger == "motion" and passage_state == "capturing":
                if ocr_attempts >= MAX_OCR_PER_PASSAGE:
                    status_line = "No plate — wait until vehicle leaves"
                    passage_state = "waiting_clear"
                else:
                    status_line = f"No plate ({ocr_attempts}/{MAX_OCR_PER_PASSAGE}) — retrying"
            else:
                status_line = "Watching… (no plate in ROI)"
            return

        cooled_until = plate_cooldown.get(plate, 0.0)
        if not force_done and now < cooled_until:
            remaining = int(cooled_until - now)
            status_line = f"{plate} on cooldown ({remaining}s)"
            if trigger == "motion":
                passage_state = "waiting_clear"
                vehicle_posted = True
            return

        if force_done:
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
            return

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
        vehicle_posted = True
        if trigger == "motion":
            passage_state = "waiting_clear"
            status_line = f"{line} — wait for clear"

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                status_line = "Camera read failed"
                time.sleep(0.05)
                continue

            now = time.time()
            present = False
            if trigger == "motion":
                present, motion_score = motion.update(crop_roi(frame))
                if present:
                    clear_streak = 0
                else:
                    clear_streak += 1

            finished: dict[str, Any] | None = None
            with ocr_lock:
                if ocr_result is not None:
                    finished = ocr_result
                    ocr_result = None
            if finished is not None:
                handle_ocr_finished(finished)

            preview = draw_overlay(
                frame,
                camera_type=camera_type,
                status_line=status_line,
                last_plate=last_plate,
                last_action=last_action,
                auto_on=auto_on,
                trigger=trigger,
                motion_score=motion_score,
            )
            if stream_on:
                frame_buffer.update(preview)
            cv2.imshow(WINDOW_NAME, preview)

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
            if force and not busy:
                start_ocr(frame.copy(), force=True)
                continue

            if busy or not auto_on:
                continue

            # ---- Motion trigger (road ANPR) ----
            if trigger == "motion":
                if passage_state == "idle":
                    if present:
                        passage_state = "capturing"
                        settle_until = now + max(0.0, args.settle)
                        ocr_attempts = 0
                        vehicle_posted = False
                        pending_plate = None
                        pending_count = 0
                        status_line = "Vehicle detected — settling…"
                        print("[TRIGGER] vehicle entered ROI")
                    else:
                        if status_line.startswith(("OCR", "No plate", "Seen", "Posting")):
                            pass
                        elif "wait" not in status_line.lower():
                            status_line = "Waiting for vehicle…"

                elif passage_state == "capturing":
                    if clear_streak >= MOTION_CLEAR_FRAMES:
                        passage_state = "idle"
                        status_line = "Waiting for vehicle…"
                        print("[TRIGGER] left before read — reset")
                        continue
                    if vehicle_posted:
                        passage_state = "waiting_clear"
                        continue
                    if now < settle_until:
                        continue
                    if ocr_attempts >= MAX_OCR_PER_PASSAGE:
                        passage_state = "waiting_clear"
                        status_line = "No plate — wait until vehicle leaves"
                        continue
                    if (now - last_ocr_at) >= args.interval:
                        start_ocr(frame.copy(), force=False)

                elif passage_state == "waiting_clear":
                    if clear_streak >= MOTION_CLEAR_FRAMES:
                        passage_state = "idle"
                        ocr_attempts = 0
                        vehicle_posted = False
                        pending_plate = None
                        pending_count = 0
                        status_line = "Ready — next vehicle"
                        print("[TRIGGER] lane clear — ready")
                    else:
                        if not status_line.endswith("clear") and "wait" not in status_line.lower():
                            status_line = "Wait until vehicle leaves…"
                continue

            # ---- Legacy interval polling ----
            due = (now - last_ocr_at) >= args.interval
            if not due:
                continue
            if not roi_has_content(frame):
                last_ocr_at = now
                status_line = "Watching… (ROI empty)"
                continue
            start_ocr(frame.copy(), force=False)

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
