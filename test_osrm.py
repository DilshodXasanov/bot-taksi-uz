import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared.utils import get_route_distance, haversine_distance

async def test():
    # Tashkent coordinates example
    # From Chorsu to Amir Temur Square
    lat1, lng1 = 41.3259, 69.2392
    lat2, lng2 = 41.3111, 69.2797
    
    hav_dist = haversine_distance(lat1, lng1, lat2, lng2)
    osrm_dist = await get_route_distance(lat1, lng1, lat2, lng2)
    
    print(f"To'g'ri chiziqli masofa (Haversine): {hav_dist} km")
    print(f"Haqiqiy marshrut (OSRM): {osrm_dist} km")

if __name__ == "__main__":
    asyncio.run(test())
