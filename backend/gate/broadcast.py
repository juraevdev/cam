from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .consumers import GateLogConsumer
from .serializers import EntryLogSerializer


def broadcast_gate_log(entry_log, event: str = 'updated') -> None:
    """Push an EntryLog create/update event to connected WebSocket clients."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    payload = EntryLogSerializer(entry_log).data
    async_to_sync(channel_layer.group_send)(
        GateLogConsumer.GROUP_NAME,
        {
            'type': 'gate_log_update',
            'event': event,
            'data': payload,
        },
    )
