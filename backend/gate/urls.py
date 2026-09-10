from django.urls import path

from .views import EntryLogListView, OpenBarrierView, ScanView

urlpatterns = [
    path('scan/', ScanView.as_view(), name='scan'),
    path('open-barrier/', OpenBarrierView.as_view(), name='open-barrier'),
    path('logs/', EntryLogListView.as_view(), name='logs'),
]
