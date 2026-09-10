from django.urls import path

from .consumers import GateLogConsumer

websocket_urlpatterns = [
    path('ws/logs/', GateLogConsumer.as_asgi()),
]
