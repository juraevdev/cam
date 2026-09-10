from django.contrib import admin

from .models import EntryLog, PassTicket, Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('license_plate', 'phone', 'created_at')
    search_fields = ('license_plate', 'phone')


@admin.register(PassTicket)
class PassTicketAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'payment_status', 'expires_at', 'created_at')
    list_filter = ('payment_status',)
    search_fields = ('vehicle__license_plate',)
    autocomplete_fields = ('vehicle',)


@admin.register(EntryLog)
class EntryLogAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'time_in', 'time_out', 'is_paid')
    list_filter = ('is_paid',)
    search_fields = ('vehicle__license_plate',)
    autocomplete_fields = ('vehicle',)
