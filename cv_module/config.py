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

# Continuous auto-scan (real-time)
# How often to run OCR while live (seconds). CPU EasyOCR is slow — 1.5–2.5s is practical.
AUTO_SCAN_INTERVAL = float(os.environ.get("SMART_GATE_SCAN_INTERVAL", "1.8"))
# Same plate won't be posted again within this window (prevents entry→instant exit).
PLATE_COOLDOWN_SECONDS = float(os.environ.get("SMART_GATE_PLATE_COOLDOWN", "12"))
# Require N identical consecutive OCR reads before posting (reduces false positives).
CONFIRM_READS = int(os.environ.get("SMART_GATE_CONFIRM_READS", "2"))
# Default ON for real-time operation; disable with --no-auto
AUTO_SCAN_ENABLED = os.environ.get("SMART_GATE_AUTO_SCAN", "1") != "0"

# UI / capture
WINDOW_NAME = "Smart Gate CV Scanner"
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("SMART_GATE_HTTP_TIMEOUT", "5"))

# Dashboard live preview (MJPEG)
STREAM_HOST = os.environ.get("SMART_GATE_STREAM_HOST", "0.0.0.0")
STREAM_PORT = int(os.environ.get("SMART_GATE_STREAM_PORT", "8081"))
STREAM_ENABLED = os.environ.get("SMART_GATE_STREAM", "1") != "0"
