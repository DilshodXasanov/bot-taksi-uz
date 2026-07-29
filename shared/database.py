import asyncpg
import logging
from shared.config import DATABASE_URL

logger = logging.getLogger(__name__)

# ==================== CONNECTION POOL ====================

_pool: asyncpg.Pool = None


async def get_pool() -> asyncpg.Pool:
    """Global connection pool ni olish. Agar mavjud bo'lmasa, yaratadi."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30
        )
        logger.info("✅ PostgreSQL connection pool yaratildi")
    return _pool


async def close_pool():
    """Connection pool ni yopish (graceful shutdown uchun)."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("🔒 PostgreSQL connection pool yopildi")


async def init_db():
    """Ma'lumotlar bazasini yaratish va jadvallarni tayyorlash."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Yo'lovchilar jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS passengers (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Haydovchilar jadvali
        await conn.execute("""
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

        # Buyurtmalar jadvali
        await conn.execute("""
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
        # status: searching, accepted, riding, completed, cancelled

        # Baholar jadvali
        await conn.execute("""
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

    logger.info("✅ Jadvallar tayyor")


# ==================== YO'LOVCHI FUNKSIYALARI ====================

async def register_passenger(telegram_id: int, full_name: str, phone: str = None):
    """Yo'lovchini ro'yxatdan o'tkazish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO passengers (telegram_id, full_name, phone) 
            VALUES ($1, $2, $3) 
            ON CONFLICT (telegram_id) DO NOTHING""",
            telegram_id, full_name, phone
        )


async def get_passenger(telegram_id: int):
    """Yo'lovchi ma'lumotlarini olish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM passengers WHERE telegram_id = $1", telegram_id
        )


async def update_passenger_phone(telegram_id: int, phone: str):
    """Yo'lovchi telefon raqamini yangilash."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE passengers SET phone = $1 WHERE telegram_id = $2",
            phone, telegram_id
        )


# ==================== HAYDOVCHI FUNKSIYALARI ====================

async def register_driver(telegram_id: int, full_name: str, phone: str,
                          car_model: str, car_number: str):
    """Haydovchini ro'yxatdan o'tkazish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO drivers 
            (telegram_id, full_name, phone, car_model, car_number) 
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (telegram_id) DO NOTHING""",
            telegram_id, full_name, phone, car_model, car_number
        )


async def get_driver(telegram_id: int):
    """Haydovchi ma'lumotlarini olish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM drivers WHERE telegram_id = $1", telegram_id
        )


async def set_driver_online(telegram_id: int, is_online: bool):
    """Haydovchini onlayn/oflayn qilish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE drivers SET is_online = $1 WHERE telegram_id = $2",
            1 if is_online else 0, telegram_id
        )


async def update_driver_location(telegram_id: int, lat: float, lng: float):
    """Haydovchi joylashuvini yangilash."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE drivers SET latitude = $1, longitude = $2 WHERE telegram_id = $3",
            lat, lng, telegram_id
        )


async def get_online_drivers():
    """Barcha onlayn haydovchilarni olish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT * FROM drivers 
            WHERE is_online = 1 AND is_approved = 1 
            AND latitude IS NOT NULL AND longitude IS NOT NULL"""
        )


async def approve_driver(telegram_id: int):
    """Haydovchini tasdiqlash (admin tomonidan)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE drivers SET is_approved = 1 WHERE telegram_id = $1",
            telegram_id
        )


async def update_driver_rating(telegram_id: int):
    """Haydovchi reytingini qayta hisoblash."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT AVG(rating)::DOUBLE PRECISION as avg_rating FROM reviews WHERE to_user = $1",
            telegram_id
        )
        if row and row['avg_rating'] is not None:
            await conn.execute(
                "UPDATE drivers SET rating = ROUND($1::numeric, 1) WHERE telegram_id = $2",
                row['avg_rating'], telegram_id
            )


# ==================== BUYURTMA FUNKSIYALARI ====================

async def create_order(passenger_id: int, pickup_lat: float, pickup_lng: float,
                       pickup_address: str = None, dest_lat: float = None,
                       dest_lng: float = None, dest_address: str = None,
                       distance_km: float = None, price: int = None):
    """Yangi buyurtma yaratish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        order_id = await conn.fetchval(
            """INSERT INTO orders 
            (passenger_id, pickup_lat, pickup_lng, pickup_address, 
             dest_lat, dest_lng, dest_address, distance_km, price, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'searching')
            RETURNING id""",
            passenger_id, pickup_lat, pickup_lng, pickup_address,
            dest_lat, dest_lng, dest_address, distance_km, price
        )
        return order_id


async def get_order(order_id: int):
    """Buyurtma ma'lumotlarini olish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM orders WHERE id = $1", order_id
        )


async def get_active_order_by_passenger(passenger_id: int):
    """Yo'lovchining faol buyurtmasini olish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """SELECT * FROM orders 
            WHERE passenger_id = $1 AND status IN ('searching', 'accepted', 'riding')
            ORDER BY created_at DESC LIMIT 1""",
            passenger_id
        )


async def get_active_order_by_driver(driver_id: int):
    """Haydovchining faol buyurtmasini olish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """SELECT * FROM orders 
            WHERE driver_id = $1 AND status IN ('accepted', 'riding')
            ORDER BY created_at DESC LIMIT 1""",
            driver_id
        )


async def accept_order(order_id: int, driver_id: int):
    """Haydovchi buyurtmani qabul qiladi. 
    Race condition himoyasi: faqat 'searching' holatdagi buyurtmani qabul qiladi.
    PostgreSQL tranzaksiya izolyatsiyasi buni xavfsiz qiladi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE orders 
            SET driver_id = $1, status = 'accepted', accepted_at = NOW()
            WHERE id = $2 AND status = 'searching'""",
            driver_id, order_id
        )
        # asyncpg execute() qaytaradi: 'UPDATE 1' yoki 'UPDATE 0'
        return result == 'UPDATE 1'


async def start_ride(order_id: int):
    """Safarni boshlash."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status = 'riding' WHERE id = $1", order_id
        )


async def update_order_price(order_id: int, price: int):
    """Buyurtma narxini yangilash."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET price = $1 WHERE id = $2", price, order_id
        )


async def complete_order(order_id: int):
    """Safarni tugatish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """UPDATE orders 
                SET status = 'completed', completed_at = NOW()
                WHERE id = $1""",
                order_id
            )
            # Haydovchining jami safarlari sonini oshirish
            row = await conn.fetchrow(
                "SELECT driver_id FROM orders WHERE id = $1", order_id
            )
            if row and row['driver_id']:
                await conn.execute(
                    "UPDATE drivers SET total_rides = total_rides + 1 WHERE telegram_id = $1",
                    row['driver_id']
                )


async def cancel_order(order_id: int):
    """Buyurtmani bekor qilish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE orders 
            SET status = 'cancelled', cancelled_at = NOW()
            WHERE id = $1""",
            order_id
        )


async def get_passenger_history(passenger_id: int, limit: int = 10):
    """Yo'lovchining safarlar tarixini olish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT o.*, d.full_name as driver_name, d.car_model, d.car_number
            FROM orders o 
            LEFT JOIN drivers d ON o.driver_id = d.telegram_id
            WHERE o.passenger_id = $1 AND o.status IN ('completed', 'cancelled')
            ORDER BY o.created_at DESC LIMIT $2""",
            passenger_id, limit
        )


async def get_driver_history(driver_id: int, limit: int = 10):
    """Haydovchining safarlar tarixini olish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT o.*, p.full_name as passenger_name, p.phone as passenger_phone
            FROM orders o 
            LEFT JOIN passengers p ON o.passenger_id = p.telegram_id
            WHERE o.driver_id = $1 AND o.status IN ('completed', 'cancelled')
            ORDER BY o.created_at DESC LIMIT $2""",
            driver_id, limit
        )


# ==================== BAHO FUNKSIYALARI ====================

async def add_review(order_id: int, from_user: int, to_user: int,
                     rating: int, comment: str = None):
    """Baho qo'shish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO reviews (order_id, from_user, to_user, rating, comment)
            VALUES ($1, $2, $3, $4, $5)""",
            order_id, from_user, to_user, rating, comment
        )
    # Reytingni yangilash
    await update_driver_rating(to_user)


# ==================== STATISTIKA ====================

async def get_driver_stats(driver_id: int):
    """Haydovchi statistikasini olish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Bugungi safarlar soni va daromad
        today = await conn.fetchrow(
            """SELECT COUNT(*) as rides, COALESCE(SUM(price), 0) as income
            FROM orders 
            WHERE driver_id = $1 AND status = 'completed' 
            AND DATE(completed_at) = CURRENT_DATE""",
            driver_id
        )

        # Jami safarlar
        total = await conn.fetchrow(
            """SELECT COUNT(*) as rides, COALESCE(SUM(price), 0) as income
            FROM orders WHERE driver_id = $1 AND status = 'completed'""",
            driver_id
        )

        return {
            "today_rides": today["rides"] if today else 0,
            "today_income": today["income"] if today else 0,
            "total_rides": total["rides"] if total else 0,
            "total_income": total["income"] if total else 0,
        }


# ==================== ADMIN FUNKSIYALARI ====================

async def get_system_stats():
    """Admin paneli uchun umumiy statistika."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        p_count = await conn.fetchval("SELECT COUNT(*) FROM passengers")
        d_count = await conn.fetchval("SELECT COUNT(*) FROM drivers")
        o_count = await conn.fetchval("SELECT COUNT(*) FROM orders")
        o_today = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = CURRENT_DATE"
        )

        return {
            "passengers": p_count,
            "drivers": d_count,
            "orders_total": o_count,
            "orders_today": o_today
        }


async def reject_driver(telegram_id: int):
    """Haydovchini o'chirish/rad etish."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM drivers WHERE telegram_id = $1", telegram_id
        )


async def get_all_users():
    """Rassilka uchun barcha user ID larni qaytaradi (haydovchi va yo'lovchi)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT telegram_id FROM passengers UNION SELECT telegram_id FROM drivers"
        )
        return [r['telegram_id'] for r in rows]


async def cleanup_zombie_orders(max_age_minutes: int = 120):
    """Accepted yoki riding holatida uzoq vaqt osilib qolgan buyurtmalarni bekor qilish.
    
    Args:
        max_age_minutes: Necha daqiqadan keyin buyurtma 'zombie' hisoblanadi (standart: 120 = 2 soat).
    
    Returns:
        Bekor qilingan buyurtmalar ro'yxati (id, passenger_id, driver_id).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Accepted holatida max_age_minutes daqiqadan ko'p turganlarni topish
            zombies = await conn.fetch(
                """SELECT id, passenger_id, driver_id FROM orders 
                WHERE status IN ('accepted', 'riding') 
                AND created_at < NOW() - make_interval(mins => $1)""",
                float(max_age_minutes)
            )

            if zombies:
                await conn.execute(
                    """UPDATE orders SET status = 'cancelled', cancelled_at = NOW() 
                    WHERE status IN ('accepted', 'riding') 
                    AND created_at < NOW() - make_interval(mins => $1)""",
                    float(max_age_minutes)
                )

            return [dict(z) for z in zombies]
