from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Sum
from django.utils.timezone import now
from datetime import timedelta
from .models import Passenger, Driver, Order
from .serializers import DriverSerializer, OrderSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stats(request):
    today = now().date()
    
    passengers = Passenger.objects.count()
    drivers = Driver.objects.count()
    orders_total = Order.objects.count()
    
    # Bugungi buyurtmalar va tushum
    today_orders = Order.objects.filter(created_at__date=today)
    orders_today = today_orders.count()
    
    completed_orders = Order.objects.filter(status='completed')
    revenue_total = completed_orders.aggregate(Sum('price'))['price__sum'] or 0
    revenue_today = completed_orders.filter(created_at__date=today).aggregate(Sum('price'))['price__sum'] or 0
    
    # Oxirgi 7 kun uchun diagramma
    chart_data = {"labels": [], "data": []}
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        cnt = Order.objects.filter(created_at__date=day).count()
        chart_data["labels"].append(day.strftime("%Y-%m-%d"))
        chart_data["data"].append(cnt)
        
    return Response({
        "passengers": passengers,
        "drivers": drivers,
        "orders_total": orders_total,
        "orders_today": orders_today,
        "revenue_total": revenue_total,
        "revenue_today": revenue_today,
        "chart": chart_data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_drivers(request):
    drivers = Driver.objects.all().order_by('is_approved', '-created_at')
    serializer = DriverSerializer(drivers, many=True)
    return Response(serializer.data)

import sys
import os
import threading
import requests
import logging

logger = logging.getLogger(__name__)

# To import shared config
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from shared.config import DRIVER_BOT_TOKEN

def _send_msg_task(chat_id, text):
    url = f"https://api.telegram.org/bot{DRIVER_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=5)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to send telegram message to {chat_id}: {e}")

def send_telegram_message(chat_id, text):
    # Run in background thread to avoid blocking HTTP response
    thread = threading.Thread(target=_send_msg_task, args=(chat_id, text))
    thread.daemon = True
    thread.start()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_driver(request, telegram_id):
    try:
        driver = Driver.objects.get(telegram_id=telegram_id)
        driver.is_approved = 1
        driver.save()
        
        # Haydovchiga xabar yuborish
        msg = ("🎉 <b>Tabriklaymiz!</b> Sizning arizangiz tasdiqlandi.\n\n"
               "Endi siz '🟢 Onlayn bo'lish' orqali buyurtmalarni qabul qilishingiz mumkin.")
        send_telegram_message(telegram_id, msg)
        
        return Response({"status": "success"})
    except Driver.DoesNotExist:
        return Response({"error": "Driver not found"}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_driver(request, telegram_id):
    try:
        driver = Driver.objects.get(telegram_id=telegram_id)
        driver.delete()
        
        # Haydovchiga xabar yuborish
        msg = "❌ Afsuski, sizning arizangiz ma'muriyat tomonidan rad etildi."
        send_telegram_message(telegram_id, msg)
        
        return Response({"status": "success"})
    except Driver.DoesNotExist:
        return Response({"error": "Driver not found"}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_live_locations(request):
    drivers = Driver.objects.filter(is_online=1).exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    serializer = DriverSerializer(drivers, many=True)
    return Response(serializer.data)
