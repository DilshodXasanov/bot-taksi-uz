"""
SQLite dan PostgreSQL ga ma'lumotlarni ko'chirish skripti.
Bu skript faqat bir marta ishlatiladi — mavjud taxi.db dagi barcha datani PostgreSQL ga o'tkazadi.

Ishlatish:
    python migrate_data.py
"""
import asyncio
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncpg
from shared.config import DATABASE_URL

# SQLite fayl yo'li
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxi.db")


async def migrate():
    # SQLite ga ulanish
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite fayl topilmadi: {SQLITE_PATH}")
        print("Agar yangi o'rnatish bo'lsa, bu skript kerak emas.")
        return

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # PostgreSQL ga ulanish
    pg_conn = await asyncpg.connect(DATABASE_URL)

    print("=" * 60)
    print("🔄 SQLite → PostgreSQL migratsiya boshlandi")
    print("=" * 60)

    try:
        # 1. Jadvallarni yaratish (init_db bilan bir xil)
        print("\n📦 Jadvallar yaratilmoqda...")
        
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS passengers (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS drivers (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT,
                car_model TEXT,
                car_number TEXT,
                is_approved INTEGER DEFAULT 0,
                is_online INTEGER DEFAULT 0,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                rating DOUBLE PRECISION DEFAULT 5.0,
                total_rides INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                passenger_id BIGINT NOT NULL,
                driver_id BIGINT,
                pickup_lat DOUBLE PRECISION NOT NULL,
                pickup_lng DOUBLE PRECISION NOT NULL,
                pickup_address TEXT,
                dest_lat DOUBLE PRECISION,
                dest_lng DOUBLE PRECISION,
                dest_address TEXT,
                distance_km DOUBLE PRECISION,
                price INTEGER,
                status TEXT DEFAULT 'searching',
                created_at TIMESTAMP DEFAULT NOW(),
                accepted_at TIMESTAMP,
                completed_at TIMESTAMP,
                cancelled_at TIMESTAMP
            )
        """)
        
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL,
                from_user BIGINT NOT NULL,
                to_user BIGINT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # 2. Passengers ko'chirish
        cursor.execute("SELECT telegram_id, full_name, phone, created_at FROM passengers")
        passengers = cursor.fetchall()
        count = 0
        for p in passengers:
            try:
                await pg_conn.execute(
                    """INSERT INTO passengers (telegram_id, full_name, phone, created_at) 
                    VALUES ($1, $2, $3, $4::timestamp)
                    ON CONFLICT (telegram_id) DO NOTHING""",
                    p['telegram_id'], p['full_name'], p['phone'],
                    p['created_at'] if p['created_at'] else None
                )
                count += 1
            except Exception as e:
                print(f"  ⚠️ Yo'lovchi {p['telegram_id']}: {e}")
        print(f"✅ Yo'lovchilar: {count}/{len(passengers)}")

        # 3. Drivers ko'chirish
        cursor.execute("""SELECT telegram_id, full_name, phone, car_model, car_number, 
                         is_approved, is_online, latitude, longitude, rating, total_rides, created_at 
                         FROM drivers""")
        drivers = cursor.fetchall()
        count = 0
        for d in drivers:
            try:
                await pg_conn.execute(
                    """INSERT INTO drivers (telegram_id, full_name, phone, car_model, car_number, 
                    is_approved, is_online, latitude, longitude, rating, total_rides, created_at) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::timestamp)
                    ON CONFLICT (telegram_id) DO NOTHING""",
                    d['telegram_id'], d['full_name'], d['phone'], d['car_model'], d['car_number'],
                    d['is_approved'], d['is_online'], d['latitude'], d['longitude'],
                    d['rating'], d['total_rides'],
                    d['created_at'] if d['created_at'] else None
                )
                count += 1
            except Exception as e:
                print(f"  ⚠️ Haydovchi {d['telegram_id']}: {e}")
        print(f"✅ Haydovchilar: {count}/{len(drivers)}")

        # 4. Orders ko'chirish
        cursor.execute("""SELECT passenger_id, driver_id, pickup_lat, pickup_lng, pickup_address, 
                         dest_lat, dest_lng, dest_address, distance_km, price, status, 
                         created_at, accepted_at, completed_at, cancelled_at 
                         FROM orders""")
        orders = cursor.fetchall()
        count = 0
        for o in orders:
            try:
                await pg_conn.execute(
                    """INSERT INTO orders (passenger_id, driver_id, pickup_lat, pickup_lng, pickup_address, 
                    dest_lat, dest_lng, dest_address, distance_km, price, status, 
                    created_at, accepted_at, completed_at, cancelled_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 
                    $12::timestamp, $13::timestamp, $14::timestamp, $15::timestamp)""",
                    o['passenger_id'], o['driver_id'], o['pickup_lat'], o['pickup_lng'],
                    o['pickup_address'], o['dest_lat'], o['dest_lng'], o['dest_address'],
                    o['distance_km'], o['price'], o['status'],
                    o['created_at'] if o['created_at'] else None,
                    o['accepted_at'] if o['accepted_at'] else None,
                    o['completed_at'] if o['completed_at'] else None,
                    o['cancelled_at'] if o['cancelled_at'] else None
                )
                count += 1
            except Exception as e:
                print(f"  ⚠️ Buyurtma: {e}")
        print(f"✅ Buyurtmalar: {count}/{len(orders)}")

        # 5. Reviews ko'chirish
        cursor.execute("SELECT order_id, from_user, to_user, rating, comment, created_at FROM reviews")
        reviews = cursor.fetchall()
        count = 0
        for r in reviews:
            try:
                await pg_conn.execute(
                    """INSERT INTO reviews (order_id, from_user, to_user, rating, comment, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6::timestamp)""",
                    r['order_id'], r['from_user'], r['to_user'], r['rating'], r['comment'],
                    r['created_at'] if r['created_at'] else None
                )
                count += 1
            except Exception as e:
                print(f"  ⚠️ Baho: {e}")
        print(f"✅ Baholar: {count}/{len(reviews)}")

        # 6. SERIAL sequence larni to'g'rilash (auto-increment)
        # PostgreSQL da INSERT qilganda id qo'lda berilmagan, shuning uchun sequence to'g'ri
        # Lekin agar orders da id lar ketma-ket bo'lishi kerak bo'lsa:
        for table in ['passengers', 'drivers', 'orders', 'reviews']:
            try:
                max_id = await pg_conn.fetchval(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
                await pg_conn.execute(f"SELECT setval('{table}_id_seq', $1, true)", max_id)
                print(f"  🔧 {table}_id_seq → {max_id}")
            except Exception as e:
                print(f"  ⚠️ Sequence {table}: {e}")

        print("\n" + "=" * 60)
        print("🎉 MIGRATSIYA MUVAFFAQIYATLI TUGADI!")
        print("=" * 60)
        print(f"\nEndi taxi.db faylini backup sifatida saqlang:")
        print(f"  mv taxi.db taxi.db.backup")

    except Exception as e:
        print(f"\n💥 XATO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sqlite_conn.close()
        await pg_conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
