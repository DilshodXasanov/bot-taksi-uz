import aiohttp
import asyncio
import logging
from math import radians, sin, cos, sqrt, atan2
from shared.config import PRICE_PER_KM, MIN_PRICE

logger = logging.getLogger(__name__)

# ==================== GLOBAL HTTP SESSION (Singleton) ====================
# Bitta session barcha OSRM so'rovlar uchun qayta ishlatiladi.
# Har safar yangi ClientSession yaratish o'rniga, bitta TCP pool ni saqlaydi.

_http_session: aiohttp.ClientSession | None = None
_OSRM_TIMEOUT = aiohttp.ClientTimeout(total=3, connect=2)


async def get_http_session() -> aiohttp.ClientSession:
    """Global HTTP session ni olish. Agar mavjud bo'lmasa yoki yopilgan bo'lsa, yangi yaratadi."""
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(
            timeout=_OSRM_TIMEOUT,
            # TCP ulanishlarni qayta ishlatish (keep-alive)
            connector=aiohttp.TCPConnector(
                limit=5,           # max 5 ta parallel ulanish
                ttl_dns_cache=300, # DNS keshni 5 daqiqa saqlash
            )
        )
        logger.info("✅ Global HTTP session yaratildi")
    return _http_session


async def close_http_session():
    """Global HTTP session ni yopish (graceful shutdown uchun)."""
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        _http_session = None
        logger.info("🔒 Global HTTP session yopildi")


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Ikki nuqta orasidagi masofani km da hisoblash (Haversine formulasi).
    """
    R = 6371  # Yer radiusi (km)

    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return round(R * c, 2)


async def get_route_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    OSRM API orqali ikkita nuqta o'rtasidagi haqiqiy mashina yo'lini (km) hisoblash.
    Agar API ishlamasa, avtomatik ravishda haversine_distance ga o'tadi.
    
    Global session ishlatiladi — har safar yangi TCP ulanish ochilmaydi.
    Qattiq 3 soniya timeout — bot hech qachon bloklanganda qotib qolmaydi.
    """
    url = f"http://router.project-osrm.org/route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=false"
    try:
        session = await get_http_session()
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    distance_meters = data["routes"][0]["distance"]
                    return round(distance_meters / 1000, 2)
    except asyncio.TimeoutError:
        logger.warning("⚠️ OSRM timeout (3s) — haversine ga o'tildi")
    except Exception as e:
        logger.warning(f"⚠️ OSRM xato: {e} — haversine ga o'tildi")
    
    # Xatolik bo'lsa yoki OSRM ishlamasa, to'g'ri chiziqli masofa qaytariladi
    return haversine_distance(lat1, lng1, lat2, lng2)


def calculate_price(distance_km: float) -> int:
    """Masofaga qarab narxni hisoblash."""
    price = int(distance_km * PRICE_PER_KM)
    return max(price, MIN_PRICE)


def format_price(price: int) -> str:
    """Narxni chiroyli formatda ko'rsatish: 15 000 so'm."""
    if price is None:
        price = 0
    return f"{price:,}".replace(",", " ") + " so'm"


def find_nearest_drivers(drivers: list, lat: float, lng: float, 
                         radius_km: float) -> list:
    """
    Berilgan nuqtaga eng yaqin haydovchilarni topish.
    Radius ichidagi haydovchilarni masofasi bo'yicha tartiblangan holda qaytaradi.
    """
    nearby = []
    for driver in drivers:
        d_lat = driver["latitude"]
        d_lng = driver["longitude"]
        if d_lat is None or d_lng is None:
            continue
        dist = haversine_distance(lat, lng, d_lat, d_lng)
        if dist <= radius_km:
            nearby.append({
                "driver": driver,
                "distance": dist
            })

    # Eng yaqindan boshlab tartiblash
    nearby.sort(key=lambda x: x["distance"])
    return nearby
