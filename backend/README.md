# Smart Gate — Backend
# =====================
#
# Project: config
# App:     gate
#
## Local (Windows / Ubuntu)
#
#   python -m venv .venv
#   source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
#   pip install -r requirements.txt
#   python manage.py migrate
#   python manage.py createsuperuser
#   python manage.py runserver 0.0.0.0:8000
#
## Endpoints
#
#   POST /api/scan/           — CV plate detection
#   POST /api/open-barrier/   — manual operator override
#   GET  /api/logs/           — recent entry logs
#   WS   /ws/logs/            — real-time log broadcast
#
## Ubuntu production notes
#
#   - Run under Daphne/Uvicorn + systemd
#   - Switch CHANNEL_LAYERS to Redis (see settings.py)
#   - Set DJANGO_SECRET_KEY, DJANGO_DEBUG=0, DJANGO_ALLOWED_HOSTS
#
