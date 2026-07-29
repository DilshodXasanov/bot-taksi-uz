import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Bot tokenlar
PASSENGER_BOT_TOKEN = os.getenv("PASSENGER_BOT_TOKEN", "")
DRIVER_BOT_TOKEN = os.getenv("DRIVER_BOT_TOKEN", "")

# Narxlar
PRICE_PER_KM = int(os.getenv("PRICE_PER_KM", "3000"))
MIN_PRICE = int(os.getenv("MIN_PRICE", "10000"))

# Timeout
ORDER_TIMEOUT = int(os.getenv("ORDER_TIMEOUT", "60"))

# Qidiruv radiusi
SEARCH_RADIUS_KM = float(os.getenv("SEARCH_RADIUS_KM", "10"))

# PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://taxi_user:taxi_secure_pass_2024@localhost:5432/taxi_db")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "taxi_db")
DB_USER = os.getenv("DB_USER", "taxi_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "taxi_secure_pass_2024")

# Redis (FSM state saqlash)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Admin ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
