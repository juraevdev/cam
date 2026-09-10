from django.db import models
from django.utils import timezone


class Vehicle(models.Model):
    license_plate = models.CharField(max_length=32, unique=True, db_index=True)
    phone = models.CharField(max_length=32, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.license_plate


class PassTicket(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        EXPIRED = 'expired', 'Expired'

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='pass_tickets',
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.vehicle.license_plate} — {self.payment_status}'

    @property
    def is_valid(self) -> bool:
        return (
            self.payment_status == self.PaymentStatus.PAID
            and self.expires_at > timezone.now()
        )


class EntryLog(models.Model):
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='entry_logs',
    )
    time_in = models.DateTimeField(default=timezone.now)
    time_out = models.DateTimeField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-time_in']

    def __str__(self) -> str:
        return f'{self.vehicle.license_plate} @ {self.time_in}'

    @property
    def action(self) -> str:
        return 'exit' if self.time_out else 'entry'

    @property
    def status(self) -> str:
        if self.time_out:
            return 'exited'
        return 'allowed' if self.is_paid else 'require_payment'
