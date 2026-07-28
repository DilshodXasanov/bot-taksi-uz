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

# Database
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "taxi.db")

# Admin ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
