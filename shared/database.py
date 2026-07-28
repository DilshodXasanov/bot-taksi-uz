import aiosqlite
from shared.config import DB_PATH


async def init_db():
    """Ma'lumotlar bazasini yaratish va jadvallarni tayyorlash."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Yo'lovchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS passengers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Haydovchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT,
                car_model TEXT,
                car_number TEXT,
                is_approved INTEGER DEFAULT 0,
                is_online INTEGER DEFAULT 0,
                latitude REAL,
                longitude REAL,
                rating REAL DEFAULT 5.0,
                total_rides INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Buyurtmalar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passenger_id INTEGER NOT NULL,
                driver_id INTEGER,
                pickup_lat REAL NOT NULL,
                pickup_lng REAL NOT NULL,
                pickup_address TEXT,
                dest_lat REAL,
                dest_lng REAL,
                dest_address TEXT,
                distance_km REAL,
                price INTEGER,
                status TEXT DEFAULT 'searching',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accepted_at TIMESTAMP,
                completed_at TIMESTAMP,
                cancelled_at TIMESTAMP,
                FOREIGN KEY (passenger_id) REFERENCES passengers(telegram_id),
                FOREIGN KEY (driver_id) REFERENCES drivers(telegram_id)
            )
        """)
        # status: searching, accepted, riding, completed, cancelled

        # Baholar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                from_user INTEGER NOT NULL,
                to_user INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)

        await db.commit()


# ==================== YO'LOVCHI FUNKSIYALARI ====================

async def register_passenger(telegram_id: int, full_name: str, phone: str = None):
    """Yo'lovchini ro'yxatdan o'tkazish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO passengers (telegram_id, full_name, phone) VALUES (?, ?, ?)",
            (telegram_id, full_name, phone)
        )
        await db.commit()


async def get_passenger(telegram_id: int):
    """Yo'lovchi ma'lumotlarini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM passengers WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            return await cursor.fetchone()


async def update_passenger_phone(telegram_id: int, phone: str):
    """Yo'lovchi telefon raqamini yangilash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE passengers SET phone = ? WHERE telegram_id = ?",
            (phone, telegram_id)
        )
        await db.commit()


# ==================== HAYDOVCHI FUNKSIYALARI ====================

async def register_driver(telegram_id: int, full_name: str, phone: str,
                          car_model: str, car_number: str):
    """Haydovchini ro'yxatdan o'tkazish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO drivers 
            (telegram_id, full_name, phone, car_model, car_number) 
            VALUES (?, ?, ?, ?, ?)""",
            (telegram_id, full_name, phone, car_model, car_number)
        )
        await db.commit()


async def get_driver(telegram_id: int):
    """Haydovchi ma'lumotlarini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM drivers WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            return await cursor.fetchone()


async def set_driver_online(telegram_id: int, is_online: bool):
    """Haydovchini onlayn/oflayn qilish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE drivers SET is_online = ? WHERE telegram_id = ?",
            (1 if is_online else 0, telegram_id)
        )
        await db.commit()


async def update_driver_location(telegram_id: int, lat: float, lng: float):
    """Haydovchi joylashuvini yangilash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE drivers SET latitude = ?, longitude = ? WHERE telegram_id = ?",
            (lat, lng, telegram_id)
        )
        await db.commit()


async def get_online_drivers():
    """Barcha onlayn haydovchilarni olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM drivers 
            WHERE is_online = 1 AND is_approved = 1 
            AND latitude IS NOT NULL AND longitude IS NOT NULL"""
        ) as cursor:
            return await cursor.fetchall()


async def approve_driver(telegram_id: int):
    """Haydovchini tasdiqlash (admin tomonidan)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE drivers SET is_approved = 1 WHERE telegram_id = ?",
            (telegram_id,)
        )
        await db.commit()


async def update_driver_rating(telegram_id: int):
    """Haydovchi reytingini qayta hisoblash."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT AVG(rating) FROM reviews WHERE to_user = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                await db.execute(
                    "UPDATE drivers SET rating = ROUND(?, 1) WHERE telegram_id = ?",
                    (row[0], telegram_id)
                )
                await db.commit()


# ==================== BUYURTMA FUNKSIYALARI ====================

async def create_order(passenger_id: int, pickup_lat: float, pickup_lng: float,
                       pickup_address: str = None, dest_lat: float = None,
                       dest_lng: float = None, dest_address: str = None,
                       distance_km: float = None, price: int = None):
    """Yangi buyurtma yaratish."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO orders 
            (passenger_id, pickup_lat, pickup_lng, pickup_address, 
             dest_lat, dest_lng, dest_address, distance_km, price, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'searching')""",
            (passenger_id, pickup_lat, pickup_lng, pickup_address,
             dest_lat, dest_lng, dest_address, distance_km, price)
        )
        await db.commit()
        return cursor.lastrowid


async def get_order(order_id: int):
    """Buyurtma ma'lumotlarini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ) as cursor:
            return await cursor.fetchone()


async def get_active_order_by_passenger(passenger_id: int):
    """Yo'lovchining faol buyurtmasini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM orders 
            WHERE passenger_id = ? AND status IN ('searching', 'accepted', 'riding')
            ORDER BY created_at DESC LIMIT 1""",
            (passenger_id,)
        ) as cursor:
            return await cursor.fetchone()


async def get_active_order_by_driver(driver_id: int):
    """Haydovchining faol buyurtmasini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM orders 
            WHERE driver_id = ? AND status IN ('accepted', 'riding')
            ORDER BY created_at DESC LIMIT 1""",
            (driver_id,)
        ) as cursor:
            return await cursor.fetchone()


async def accept_order(order_id: int, driver_id: int):
    """Haydovchi buyurtmani qabul qiladi."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Bitta so'rovda tekshirish va yangilash (Race condition ni oldini oladi)
        cursor = await db.execute(
            """UPDATE orders 
            SET driver_id = ?, status = 'accepted', accepted_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'searching'""",
            (driver_id, order_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def start_ride(order_id: int):
    """Safarni boshlash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = 'riding' WHERE id = ?", (order_id,)
        )
        await db.commit()


async def update_order_price(order_id: int, price: int):
    """Buyurtma narxini yangilash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET price = ? WHERE id = ?", (price, order_id)
        )
        await db.commit()


async def complete_order(order_id: int):
    """Safarni tugatish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (order_id,)
        )
        # Haydovchining jami safarlari sonini oshirish
        async with db.execute(
            "SELECT driver_id FROM orders WHERE id = ?", (order_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                await db.execute(
                    "UPDATE drivers SET total_rides = total_rides + 1 WHERE telegram_id = ?",
                    (row[0],)
                )
        await db.commit()


async def cancel_order(order_id: int):
    """Buyurtmani bekor qilish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders 
            SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (order_id,)
        )
        await db.commit()


async def get_passenger_history(passenger_id: int, limit: int = 10):
    """Yo'lovchining safarlar tarixini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.*, d.full_name as driver_name, d.car_model, d.car_number
            FROM orders o 
            LEFT JOIN drivers d ON o.driver_id = d.telegram_id
            WHERE o.passenger_id = ? AND o.status IN ('completed', 'cancelled')
            ORDER BY o.created_at DESC LIMIT ?""",
            (passenger_id, limit)
        ) as cursor:
            return await cursor.fetchall()


async def get_driver_history(driver_id: int, limit: int = 10):
    """Haydovchining safarlar tarixini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.*, p.full_name as passenger_name, p.phone as passenger_phone
            FROM orders o 
            LEFT JOIN passengers p ON o.passenger_id = p.telegram_id
            WHERE o.driver_id = ? AND o.status IN ('completed', 'cancelled')
            ORDER BY o.created_at DESC LIMIT ?""",
            (driver_id, limit)
        ) as cursor:
            return await cursor.fetchall()


# ==================== BAHO FUNKSIYALARI ====================

async def add_review(order_id: int, from_user: int, to_user: int,
                     rating: int, comment: str = None):
    """Baho qo'shish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO reviews (order_id, from_user, to_user, rating, comment)
            VALUES (?, ?, ?, ?, ?)""",
            (order_id, from_user, to_user, rating, comment)
        )
        await db.commit()
    # Reytingni yangilash
    await update_driver_rating(to_user)


# ==================== STATISTIKA ====================

async def get_driver_stats(driver_id: int):
    """Haydovchi statistikasini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Bugungi safarlar soni va daromad
        async with db.execute(
            """SELECT COUNT(*) as rides, COALESCE(SUM(price), 0) as income
            FROM orders 
            WHERE driver_id = ? AND status = 'completed' 
            AND DATE(completed_at) = DATE('now')""",
            (driver_id,)
        ) as cursor:
            today = await cursor.fetchone()

        # Jami safarlar
        async with db.execute(
            """SELECT COUNT(*) as rides, COALESCE(SUM(price), 0) as income
            FROM orders WHERE driver_id = ? AND status = 'completed'""",
            (driver_id,)
        ) as cursor:
            total = await cursor.fetchone()

        return {
            "today_rides": today["rides"] if today else 0,
            "today_income": today["income"] if today else 0,
            "total_rides": total["rides"] if total else 0,
            "total_income": total["income"] if total else 0,
        }


# ==================== ADMIN FUNKSIYALARI ====================

async def get_system_stats():
    """Admin paneli uchun umumiy statistika."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        async with db.execute("SELECT COUNT(*) FROM passengers") as cursor:
            p_count = (await cursor.fetchone())[0]
            
        async with db.execute("SELECT COUNT(*) FROM drivers") as cursor:
            d_count = (await cursor.fetchone())[0]
            
        async with db.execute("SELECT COUNT(*) FROM orders") as cursor:
            o_count = (await cursor.fetchone())[0]
            
        async with db.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')") as cursor:
            o_today = (await cursor.fetchone())[0]

        return {
            "passengers": p_count,
            "drivers": d_count,
            "orders_total": o_count,
            "orders_today": o_today
        }


async def reject_driver(telegram_id: int):
    """Haydovchini o'chirish/rad etish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM drivers WHERE telegram_id = ?", (telegram_id,))
        await db.commit()


async def get_all_users():
    """Rassilka uchun barcha user ID larni qaytaradi (haydovchi va yo'lovchi)."""
    users = set()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT telegram_id FROM passengers") as cursor:
            rows = await cursor.fetchall()
            for r in rows: users.add(r[0])
            
        async with db.execute("SELECT telegram_id FROM drivers") as cursor:
            rows = await cursor.fetchall()
            for r in rows: users.add(r[0])
            
    return list(users)


async def cleanup_zombie_orders(max_age_minutes: int = 120):
    """Accepted yoki riding holatida uzoq vaqt osilib qolgan buyurtmalarni bekor qilish.
    
    Args:
        max_age_minutes: Necha daqiqadan keyin buyurtma 'zombie' hisoblanadi (standart: 120 = 2 soat).
    
    Returns:
        Bekor qilingan buyurtmalar ro'yxati (id, passenger_id, driver_id).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Accepted holatida max_age_minutes daqiqadan ko'p turganlarni topish
        async with db.execute(
            """SELECT id, passenger_id, driver_id FROM orders 
            WHERE status IN ('accepted', 'riding') 
            AND created_at < datetime('now', ? || ' minutes')""",
            (f"-{max_age_minutes}",)
        ) as cursor:
            zombies = await cursor.fetchall()
        
        if zombies:
            await db.execute(
                """UPDATE orders SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP 
                WHERE status IN ('accepted', 'riding') 
                AND created_at < datetime('now', ? || ' minutes')""",
                (f"-{max_age_minutes}",)
            )
            await db.commit()
        
        return [dict(z) for z in zombies]
