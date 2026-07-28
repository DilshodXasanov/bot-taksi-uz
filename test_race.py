import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared.database import accept_order, create_order, get_order, init_db

async def test_race_condition():
    # 1. Initialize DB and create a dummy order
    await init_db()
    # Assume passenger_id = 12345
    order_id = await create_order(
        passenger_id=12345, 
        pickup_lat=41.0, pickup_lng=69.0, 
        distance_km=10, price=20000
    )
    
    print(f"Yaratilgan buyurtma ID: {order_id}")
    
    # 2. Simulate 3 drivers trying to accept the same order concurrently
    driver_ids = [111, 222, 333]
    
    async def try_accept(driver_id):
        # O'zgarishsiz accept_order poygada hammaga True qaytarishi mumkin edi
        # Lekin yangilanganida faqat bitta haydovchiga True qaytaradi
        success = await accept_order(order_id, driver_id)
        if success:
            print(f"SUCCESS: Haydovchi {driver_id} buyurtmani OLA BILDI!")
        else:
            print(f"FAILED: Haydovchi {driver_id} buyurtmani ololmadi.")
            
    # Ikkita-uchta haydovchi bir vaqtning o'zida harakat qilsa
    await asyncio.gather(*(try_accept(d_id) for d_id in driver_ids))
    
    # 3. Yekuniy holat
    order = await get_order(order_id)
    print(f"Buyurtma yakuniy egasi (driver_id): {order['driver_id']}")
    print(f"Buyurtma holati: {order['status']}")

if __name__ == "__main__":
    asyncio.run(test_race_condition())
