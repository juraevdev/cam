import json

from channels.generic.websocket import AsyncWebsocketConsumer


class GateLogConsumer(AsyncWebsocketConsumer):
    """Broadcasts EntryLog create/update events to the operator dashboard."""

    GROUP_NAME = 'gate_logs'

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'connection',
                    'message': 'Connected to gate log stream',
                }
            )
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Read-only feed for the admin dashboard.
        return

    async def gate_log_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'gate_log_update',
                    'event': event.get('event'),
                    'data': event.get('data'),
                }
            )
        )
