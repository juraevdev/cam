# Smart Gate — CV Module
# ======================
#
# Reads a webcam (or RTSP camera), runs EasyOCR when you press **S**,
# cleans the detected plate text, and POSTs to Django:
#
#   POST {API}/api/scan/
#   {"license_plate": "01A123AA", "camera_type": "auto"|"entry"|"exit"}
#
## Install (Ubuntu)
#
#   sudo apt update
#   sudo apt install -y python3-pip python3-venv libgl1 libglib2.0-0
#   cd cv_module
#   python3 -m venv .venv
#   source .venv/bin/activate
#   pip install -r requirements.txt
#
## Run (backend must be up on :8000)
#
#   # Real-time auto scan (default) — plate in green box → auto POST
#   python scanner.py --type auto --api http://127.0.0.1:8000
#
#   # Separate entry / exit cameras (production)
#   python scanner.py --type entry --camera 0
#   python scanner.py --type exit  --camera 1
#
#   # Manual only
#   python scanner.py --no-auto
#
## Controls
#
#   (auto) continuously OCR green ROI every ~1.8s
#   S — force immediate scan
#   A — toggle auto on/off
#   C — cycle camera type (auto / entry / exit)
#   Q — quit
#
# Same plate is ignored for ~12s after a successful POST
# (so entry is not instantly treated as exit on one camera).
#
## Environment overrides
#
#   SMART_GATE_API_URL=http://127.0.0.1:8000
#   SMART_GATE_CAMERA_INDEX=0
#   SMART_GATE_CAMERA_TYPE=entry
#   SMART_GATE_OCR_GPU=0
#
## Zomin post tip
#
#   Run two processes:
#     Entry lane:  python scanner.py --type entry --camera 0
#     Exit lane:   python scanner.py --type exit  --camera 1
#
## Test without camera / OCR
#
#   (backend must be running; payment is OFF by default)
#   pip install requests
#   python simulate_scan.py 01A123AA --roundtrip
#
