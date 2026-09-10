from rest_framework import serializers

from .models import EntryLog, PassTicket, Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'license_plate', 'phone', 'created_at']
        read_only_fields = ['id', 'created_at']


class PassTicketSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    vehicle_id = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.all(),
        source='vehicle',
        write_only=True,
    )
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = PassTicket
        fields = [
            'id',
            'vehicle',
            'vehicle_id',
            'payment_status',
            'expires_at',
            'created_at',
            'is_valid',
        ]
        read_only_fields = ['id', 'created_at', 'is_valid']


class EntryLogSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    license_plate = serializers.CharField(source='vehicle.license_plate', read_only=True)
    action = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = EntryLog
        fields = [
            'id',
            'vehicle',
            'license_plate',
            'time_in',
            'time_out',
            'is_paid',
            'action',
            'status',
            'created_at',
        ]
        read_only_fields = fields


class ScanSerializer(serializers.Serializer):
    CAMERA_ENTRY = 'entry'
    CAMERA_EXIT = 'exit'
    CAMERA_AUTO = 'auto'
    CAMERA_TYPES = (CAMERA_ENTRY, CAMERA_EXIT, CAMERA_AUTO)

    license_plate = serializers.CharField(max_length=32)
    camera_type = serializers.ChoiceField(
        choices=CAMERA_TYPES,
        required=False,
        default=CAMERA_AUTO,
    )
    image_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)

    def validate_license_plate(self, value: str) -> str:
        cleaned = ''.join(value.split()).upper()
        if not cleaned:
            raise serializers.ValidationError('license_plate cannot be empty.')
        return cleaned


class OpenBarrierSerializer(serializers.Serializer):
    entry_log_id = serializers.IntegerField(required=False)
    license_plate = serializers.CharField(max_length=32, required=False)

    def validate(self, attrs):
        if not attrs.get('entry_log_id') and not attrs.get('license_plate'):
            raise serializers.ValidationError(
                'Provide entry_log_id or license_plate.'
            )
        if attrs.get('license_plate'):
            attrs['license_plate'] = ''.join(attrs['license_plate'].split()).upper()
        return attrs
