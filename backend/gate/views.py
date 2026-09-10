from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .broadcast import broadcast_gate_log
from .models import EntryLog, PassTicket, Vehicle
from .serializers import (
    EntryLogSerializer,
    OpenBarrierSerializer,
    ScanSerializer,
)


class ScanView(APIView):
    """
    POST /api/scan/

    Called by the CV module when a license plate is detected.

    Body:
      {
        "license_plate": "01A123AA",
        "camera_type": "entry" | "exit" | "auto"  (optional, default auto)
      }

    Auto mode:
      - If the vehicle has an open EntryLog (time_out is null) -> treat as exit
      - Otherwise -> treat as entry

    When settings.GATE_REQUIRE_PAYMENT is False (default for testing),
    every successful entry/exit returns action=open_barrier.
    """

    def post(self, request, *args, **kwargs):
        serializer = ScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        license_plate = serializer.validated_data['license_plate']
        camera_type = serializer.validated_data.get(
            'camera_type', ScanSerializer.CAMERA_AUTO
        )

        vehicle, _ = Vehicle.objects.get_or_create(license_plate=license_plate)
        active_entry = (
            EntryLog.objects.filter(vehicle=vehicle, time_out__isnull=True)
            .order_by('-time_in')
            .first()
        )

        if camera_type == ScanSerializer.CAMERA_AUTO:
            camera_type = (
                ScanSerializer.CAMERA_EXIT
                if active_entry
                else ScanSerializer.CAMERA_ENTRY
            )

        if camera_type == ScanSerializer.CAMERA_ENTRY:
            return self._handle_entry(vehicle)
        return self._handle_exit(vehicle, active_entry)

    def _payment_required(self) -> bool:
        return bool(getattr(settings, 'GATE_REQUIRE_PAYMENT', False))

    def _has_valid_pass(self, vehicle: Vehicle) -> bool:
        now = timezone.now()
        return PassTicket.objects.filter(
            vehicle=vehicle,
            payment_status=PassTicket.PaymentStatus.PAID,
            expires_at__gt=now,
        ).exists()

    def _handle_entry(self, vehicle: Vehicle) -> Response:
        if self._payment_required():
            is_paid = self._has_valid_pass(vehicle)
        else:
            # Testing / camera-only mode: treat as allowed.
            is_paid = True

        entry_log = EntryLog.objects.create(
            vehicle=vehicle,
            time_in=timezone.now(),
            is_paid=is_paid,
        )
        broadcast_gate_log(entry_log, event='created')

        if is_paid:
            return Response(
                {
                    'action': 'open_barrier',
                    'status': 'success',
                    'direction': 'entry',
                    'payment_enforced': self._payment_required(),
                    'entry_log': EntryLogSerializer(entry_log).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                'action': 'require_payment',
                'status': 'payment_required',
                'direction': 'entry',
                'payment_enforced': True,
                'entry_log': EntryLogSerializer(entry_log).data,
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )

    def _handle_exit(
        self,
        vehicle: Vehicle,
        active_entry: EntryLog | None,
    ) -> Response:
        if active_entry is None:
            active_entry = (
                EntryLog.objects.filter(vehicle=vehicle, time_out__isnull=True)
                .order_by('-time_in')
                .first()
            )

        if active_entry is None:
            return Response(
                {
                    'action': 'deny',
                    'status': 'no_active_entry',
                    'detail': 'No active entry found for this vehicle.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if self._payment_required():
            if not active_entry.is_paid and not self._has_valid_pass(vehicle):
                broadcast_gate_log(active_entry, event='updated')
                return Response(
                    {
                        'action': 'require_payment',
                        'status': 'payment_required',
                        'direction': 'exit',
                        'payment_enforced': True,
                        'entry_log': EntryLogSerializer(active_entry).data,
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        active_entry.time_out = timezone.now()
        update_fields = ['time_out']
        if not active_entry.is_paid:
            active_entry.is_paid = True
            update_fields.append('is_paid')
        active_entry.save(update_fields=update_fields)

        broadcast_gate_log(active_entry, event='updated')
        return Response(
            {
                'action': 'open_barrier',
                'status': 'success',
                'direction': 'exit',
                'payment_enforced': self._payment_required(),
                'entry_log': EntryLogSerializer(active_entry).data,
            },
            status=status.HTTP_200_OK,
        )


class OpenBarrierView(APIView):
    """
    POST /api/open-barrier/

    Manual operator override from the dashboard.

    Body:
      {"entry_log_id": 1}
      or
      {"license_plate": "01A123AA"}
    """

    def post(self, request, *args, **kwargs):
        serializer = OpenBarrierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entry_log = self._resolve_entry_log(serializer.validated_data)
        if entry_log is None:
            return Response(
                {'detail': 'Entry log not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        entry_log.is_paid = True
        entry_log.save(update_fields=['is_paid'])
        broadcast_gate_log(entry_log, event='updated')

        return Response(
            {
                'action': 'open_barrier',
                'status': 'success',
                'entry_log': EntryLogSerializer(entry_log).data,
            },
            status=status.HTTP_200_OK,
        )

    def _resolve_entry_log(self, data) -> EntryLog | None:
        entry_log_id = data.get('entry_log_id')
        if entry_log_id:
            return (
                EntryLog.objects.select_related('vehicle')
                .filter(pk=entry_log_id)
                .first()
            )

        license_plate = data.get('license_plate')
        vehicle = Vehicle.objects.filter(license_plate=license_plate).first()
        if vehicle is None:
            return None
        return (
            EntryLog.objects.filter(vehicle=vehicle, time_out__isnull=True)
            .order_by('-time_in')
            .first()
        )


class EntryLogListView(APIView):
    """GET /api/logs/ — recent entry logs for the dashboard bootstrap."""

    def get(self, request, *args, **kwargs):
        logs = EntryLog.objects.select_related('vehicle').all()[:100]
        return Response(EntryLogSerializer(logs, many=True).data)
