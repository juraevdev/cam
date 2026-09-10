"""
Configuration for the Smart Gate CV scanner.

Override via environment variables or CLI flags in scanner.py.
"""

from __future__ import annotations

import os

# Django backend
API_BASE_URL = os.environ.get("SMART_GATE_API_URL", "http://127.0.0.1:8000").rstrip("/")
SCAN_ENDPOINT = f"{API_BASE_URL}/api/scan/"

# Camera
CAMERA_INDEX = int(os.environ.get("SMART_GATE_CAMERA_INDEX", "0"))
# entry | exit | auto  (auto: backend decides based on open EntryLog)
CAMERA_TYPE = os.environ.get("SMART_GATE_CAMERA_TYPE", "auto")

# OCR
OCR_LANGUAGES = ["en"]
OCR_GPU = os.environ.get("SMART_GATE_OCR_GPU", "0") == "1"
MIN_OCR_CONFIDENCE = float(os.environ.get("SMART_GATE_MIN_OCR_CONF", "0.22"))

# Trigger mode: motion (road-camera style) | interval (legacy polling)
TRIGGER_MODE = os.environ.get("SMART_GATE_TRIGGER", "motion").strip().lower()

# Interval between OCR retries while a vehicle is still in the ROI (motion mode),
# or between polls (interval mode). CPU EasyOCR is slow — 2.5–4s is practical.
AUTO_SCAN_INTERVAL = float(os.environ.get("SMART_GATE_SCAN_INTERVAL", "2.8"))
# Same plate won't be posted again within this window (prevents entry→instant exit).
PLATE_COOLDOWN_SECONDS = float(os.environ.get("SMART_GATE_PLATE_COOLDOWN", "20"))
# Require N identical consecutive OCR reads before posting (reduces false positives).
CONFIRM_READS = int(os.environ.get("SMART_GATE_CONFIRM_READS", "2"))
# Default ON for real-time operation; disable with --no-auto
AUTO_SCAN_ENABLED = os.environ.get("SMART_GATE_AUTO_SCAN", "1") != "0"
# Skip OCR when green ROI has almost no edges (empty scene) — interval mode.
ROI_MIN_EDGE_RATIO = float(os.environ.get("SMART_GATE_ROI_EDGE_MIN", "0.012"))

# Motion trigger (road ANPR style)
MOTION_DIFF_THRESHOLD = int(os.environ.get("SMART_GATE_MOTION_DIFF", "28"))
MOTION_MIN_CHANGE = float(os.environ.get("SMART_GATE_MOTION_MIN", "0.035"))
# Wait after motion starts so the plate is centered / sharp before OCR.
MOTION_SETTLE_SECONDS = float(os.environ.get("SMART_GATE_SETTLE", "0.6"))
# Frames without motion required before accepting the next vehicle.
MOTION_CLEAR_FRAMES = int(os.environ.get("SMART_GATE_CLEAR_FRAMES", "18"))
# Max OCR attempts per vehicle passage (then wait until lane clears).
MAX_OCR_PER_PASSAGE = int(os.environ.get("SMART_GATE_OCR_PER_PASS", "4"))

# UI / capture
WINDOW_NAME = "Smart Gate CV Scanner"
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("SMART_GATE_HTTP_TIMEOUT", "5"))

# Dashboard live preview (MJPEG)
STREAM_HOST = os.environ.get("SMART_GATE_STREAM_HOST", "0.0.0.0")
STREAM_PORT = int(os.environ.get("SMART_GATE_STREAM_PORT", "8081"))
STREAM_ENABLED = os.environ.get("SMART_GATE_STREAM", "1") != "0"
