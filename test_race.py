"""
Race condition testi — PostgreSQL bilan.
Bir vaqtning o'zida 3 ta haydovchi bitta buyurtmani qabul qilishga harakat qiladi.
Faqat bitta haydovchi muvaffaqiyatli bo'lishi kerak.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared.database import accept_order, create_order, get_order, init_db, close_pool


async def test_race_condition():
    # 1. Initialize DB
    await init_db()
    
    # Dummy buyurtma yaratish (passenger_id = 12345)
    order_id = await create_order(
        passenger_id=12345, 
        pickup_lat=41.0, pickup_lng=69.0, 
        distance_km=10, price=20000
    )
    
    print(f"✅ Yaratilgan buyurtma ID: {order_id}")
    
    # 2. 3 ta haydovchi bir vaqtning o'zida buyurtmani qabul qilishga harakat qiladi
    driver_ids = [111, 222, 333]
    results = {}
    
    async def try_accept(driver_id):
        success = await accept_order(order_id, driver_id)
        results[driver_id] = success
        if success:
            print(f"  ✅ SUCCESS: Haydovchi {driver_id} buyurtmani OLA BILDI!")
        else:
            print(f"  ❌ FAILED: Haydovchi {driver_id} buyurtmani ololmadi.")
            
    # Uchta haydovchi bir vaqtning o'zida harakat qiladi
    print(f"\n🏁 {len(driver_ids)} ta haydovchi bir vaqtda buyurtma #{order_id} ni olishga harakat qilmoqda...")
    await asyncio.gather(*(try_accept(d_id) for d_id in driver_ids))
    
    # 3. Natijalarni tekshirish
    success_count = sum(1 for v in results.values() if v)
    order = await get_order(order_id)
    
    print(f"\n📊 Natija:")
    print(f"  Muvaffaqiyatli qabul qilganlar soni: {success_count}")
    print(f"  Buyurtma egasi (driver_id): {order['driver_id']}")
    print(f"  Buyurtma holati: {order['status']}")
    
    # Faqat bitta haydovchi muvaffaqiyatli bo'lishi KERAK
    if success_count == 1:
        print(f"\n🎉 TEST PASSED! Race condition himoyasi ishlaydi!")
    else:
        print(f"\n💥 TEST FAILED! {success_count} ta haydovchi qabul qildi (faqat 1 bo'lishi kerak)")
    
    await close_pool()


if __name__ == "__main__":
    asyncio.run(test_race_condition())
