from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('stats/', views.get_stats, name='api-stats'),
    path('drivers/', views.get_drivers, name='api-drivers'),
    path('drivers/<int:telegram_id>/approve/', views.approve_driver, name='api-approve'),
    path('drivers/<int:telegram_id>/reject/', views.reject_driver, name='api-reject'),
    path('live/', views.get_live_locations, name='api-live'),
]
