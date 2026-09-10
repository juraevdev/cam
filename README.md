# Smart Gate & Parking Management System

Pullik kirish posti / smart gate: kamera raqamni o‘qiydi → server yozadi →
operator dashboard jonli kuzatadi. To‘lov moduli keyinroq yoqiladi.

## Structure

```
backend/      Django project `config` + app `gate` (REST + WebSockets)
frontend/     React + TypeScript + Vite operator dashboard
cv_module/    OpenCV + EasyOCR real-time scanner + MJPEG stream
```

## Requirements

- Python 3.11+
- Node.js 20+
- Webcam (or RTSP URL)

## Quick start

### 1) Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# Ubuntu:  source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### 2) Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

### 3) CV scanner (auto OCR + live MJPEG on :8081)
```bash
cd cv_module
pip install -r requirements.txt
# After EasyOCR install (Windows):
#   pip uninstall -y opencv-python-headless
#   pip install --force-reinstall opencv-python
python scanner.py --type auto --api http://127.0.0.1:8000
```

Dashboard camera panel reads: `http://127.0.0.1:8081/stream`

## API

| Endpoint | Role |
|---|---|
| `POST /api/scan/` | CV posts detected plate |
| `POST /api/open-barrier/` | Manual operator override |
| `GET /api/logs/` | Recent entry/exit logs |
| `WS /ws/logs/` | Real-time dashboard feed |

## Payment mode

Default: **OFF** (`GATE_REQUIRE_PAYMENT=False`) — every scan opens the barrier
and still logs `time_in` / `time_out`.

Enable later:
```bash
export SMART_GATE_REQUIRE_PAYMENT=1
```

Camera-less API test:
```bash
cd cv_module
python simulate_scan.py 01A123AA --roundtrip
```

## Production notes (Ubuntu)

- Run Django with Daphne/Uvicorn + systemd
- Switch Channels to Redis (`channels_redis`)
- Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`
- Entry/exit lanes: two scanner processes (`--type entry` / `--type exit`)

## License

Private / internal use unless otherwise specified.
