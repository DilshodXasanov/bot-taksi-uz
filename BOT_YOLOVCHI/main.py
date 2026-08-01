import sys
import os
import asyncio
import logging

# Loyiha root papkasini Python path ga qo'shish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder

from shared.config import PASSENGER_BOT_TOKEN, DRIVER_BOT_TOKEN, SEARCH_RADIUS_KM, ORDER_TIMEOUT, REDIS_URL
from shared.database import (
    init_db, register_passenger, get_passenger, update_passenger_phone,
    create_order, get_order, get_active_order_by_passenger, cancel_order,
    get_online_drivers, get_passenger_history, add_review, accept_order
)
from shared.utils import get_route_distance, haversine_distance, calculate_price, format_price, find_nearest_drivers
from keyboards import (
    main_menu_kb, phone_kb, location_kb, confirm_order_kb,
    cancel_order_kb, rating_kb, skip_dest_kb
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot va Dispatcher (RedisStorage — bot restart bo'lganda state saqlanadi)
bot = Bot(token=PASSENGER_BOT_TOKEN)
storage = RedisStorage.from_url(REDIS_URL, key_builder=DefaultKeyBuilder(prefix="passenger"))
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Haydovchi botiga xabar yuborish uchun
driver_bot = Bot(token=DRIVER_BOT_TOKEN)


# ==================== HOLATLAR (States) ====================

class Registration(StatesGroup):
    phone = State()


class OrderState(StatesGroup):
    pickup_location = State()      # Qayerdan olish
    destination = State()          # Qayerga borish
    confirm = State()              # Tasdiqlash
    waiting_driver = State()       # Haydovchi kutish
    riding = State()               # Safarda
    rating = State()               # Baho berish


# ==================== /start KOMANDASI ====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    passenger = await get_passenger(message.from_user.id)

    if passenger:
        await message.answer(
            f"🚖 Xush kelibsiz, {passenger['full_name']}!\n\n"
            "Taksi chaqirish uchun quyidagi tugmani bosing:",
            reply_markup=main_menu_kb()
        )
    else:
        # Ro'yxatdan o'tkazish
        await register_passenger(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name
        )
        await message.answer(
            f"👋 Salom, {message.from_user.full_name}!\n\n"
            "🚖 <b>Taksi botimizga xush kelibsiz!</b>\n\n"
            "Buyurtma berish uchun telefon raqamingizni yuboring:",
            reply_markup=phone_kb(),
            parse_mode="HTML"
        )
        await state.set_state(Registration.phone)


# ==================== RO'YXATDAN O'TISH ====================

@router.message(Registration.phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await update_passenger_phone(message.from_user.id, phone)
    await state.clear()
    await message.answer(
        "✅ Telefon raqamingiz saqlandi!\n\n"
        "Endi taksi chaqirishingiz mumkin 🚖",
        reply_markup=main_menu_kb()
    )


@router.message(Registration.phone, F.text == "❌ Bekor qilish")
async def cancel_registration(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Keyinroq telefon raqamini yuborishingiz mumkin.\n"
        "Taksi chaqirish uchun quyidagi tugmani bosing:",
        reply_markup=main_menu_kb()
    )


# ==================== TAKSI CHAQIRISH ====================

@router.message(F.text == "🚖 Taksi chaqirish")
async def order_taxi(message: Message, state: FSMContext):
    # Avval faol buyurtma bor-yo'qligini tekshiramiz
    active = await get_active_order_by_passenger(message.from_user.id)
    if active:
        await message.answer(
            "⚠️ Sizda faol buyurtma mavjud!\n"
            "Avval uni tugating yoki bekor qiling."
        )
        return

    await message.answer(
        "📍 <b>Qayerdasiz?</b>\n\n"
        "Hozirgi joylashuvingizni yuboring:",
        reply_markup=location_kb("📍 Mening joylashuvim"),
        parse_mode="HTML"
    )
    await state.set_state(OrderState.pickup_location)


# Joylashuvni qabul qilish (pickup)
@router.message(OrderState.pickup_location, F.location)
async def process_pickup_location(message: Message, state: FSMContext):
    await state.update_data(
        pickup_lat=message.location.latitude,
        pickup_lng=message.location.longitude
    )
    await message.answer(
        "🏁 <b>Qayerga borasiz?</b>\n\n"
        "Manzil joylashuvini yuboring yoki haydovchiga aytasiz:",
        reply_markup=location_kb("📍 Manzil joylashuvini yuborish"),
        parse_mode="HTML"
    )
    # "Haydovchiga aytaman" tugmasini ham ko'rsatamiz
    await message.answer(
        "Yoki manzilni haydovchiga aytmoqchimisiz?",
        reply_markup=skip_dest_kb()
    )
    await state.set_state(OrderState.destination)


# Manzilni qabul qilish
@router.message(OrderState.destination, F.location)
async def process_destination(message: Message, state: FSMContext):
    data = await state.get_data()
    pickup_lat = data["pickup_lat"]
    pickup_lng = data["pickup_lng"]
    dest_lat = message.location.latitude
    dest_lng = message.location.longitude

    # Masofani hisoblash (Haqiqiy mashina marshruti)
    distance = await get_route_distance(pickup_lat, pickup_lng, dest_lat, dest_lng)
    price = calculate_price(distance)

    await state.update_data(
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        distance=distance,
        price=price
    )

    await message.answer(
        f"🚖 <b>Buyurtma ma'lumotlari:</b>\n\n"
        f"📏 Masofa: <b>{distance} km</b>\n"
        f"💰 Narx: <b>{format_price(price)}</b>\n\n"
        f"Buyurtmani tasdiqlaysizmi?",
        reply_markup=confirm_order_kb(format_price(price), f"{distance} km"),
        parse_mode="HTML"
    )
    await state.set_state(OrderState.confirm)


# Manzilni "haydovchiga aytaman" deb o'tkazib yuborish
@router.callback_query(OrderState.destination, F.data == "skip_destination")
async def skip_destination(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = calculate_price(3)  # Minimal narx

    await state.update_data(
        dest_lat=None,
        dest_lng=None,
        distance=None,
        price=price
    )

    await callback.message.edit_text(
        f"🚖 <b>Buyurtma ma'lumotlari:</b>\n\n"
        f"📍 Joylashuv: yuborildi\n"
        f"🏁 Manzil: haydovchiga aytasiz\n"
        f"💰 Boshlang'ich narx: <b>{format_price(price)}</b>\n"
        f"ℹ️ Aniq narx masofa bo'yicha hisoblanadi\n\n"
        f"Buyurtmani tasdiqlaysizmi?",
        reply_markup=confirm_order_kb(format_price(price), "noma'lum"),
        parse_mode="HTML"
    )
    await state.set_state(OrderState.confirm)


# ==================== BUYURTMANI TASDIQLASH ====================

@router.callback_query(OrderState.confirm, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    # Buyurtma yaratish
    order_id = await create_order(
        passenger_id=callback.from_user.id,
        pickup_lat=data["pickup_lat"],
        pickup_lng=data["pickup_lng"],
        dest_lat=data.get("dest_lat"),
        dest_lng=data.get("dest_lng"),
        distance_km=data.get("distance"),
        price=data.get("price")
    )

    await state.update_data(order_id=order_id)

    await callback.message.edit_text(
        f"✅ <b>Buyurtma #{order_id} qabul qilindi!</b>\n\n"
        f"🔍 Sizga eng yaqin haydovchi qidirilmoqda...\n"
        f"⏳ Iltimos, kuting.",
        parse_mode="HTML"
    )

    await callback.message.answer(
        "Kutish vaqtida buyurtmani bekor qilishingiz mumkin:",
        reply_markup=cancel_order_kb()
    )

    await state.set_state(OrderState.waiting_driver)

    # Yaqin haydovchilarga xabar yuborish
    found = await notify_nearby_drivers(order_id, data)
    
    # Taymerni faqat haydovchi topilganda ishga tushirish
    if found:
        asyncio.create_task(order_timeout_task(order_id, callback.from_user.id, state))
    else:
        await state.clear()

async def order_timeout_task(order_id: int, passenger_id: int, state: FSMContext = None):
    """Zombi buyurtmalarni o'chirish."""
    await asyncio.sleep(ORDER_TIMEOUT)
    order = await get_order(order_id)
    if order and order["status"] == "searching":
        await cancel_order(order_id)
        if state:
            await state.clear()
        try:
            await bot.send_message(
                passenger_id,
                "⏳ Afsuski, barcha haydovchilar band.\nBuyurtma avtomatik bekor qilindi.\n"
                "Iltimos, birozdan so'ng qayta urinib ko'ring.",
                reply_markup=main_menu_kb()
            )
        except Exception as e:
            logger.error(f"Taymer xatosi: {e}")



@router.callback_query(OrderState.confirm, F.data == "cancel_order")
async def cancel_during_confirm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await callback.message.answer(
        "Asosiy menyu:",
        reply_markup=main_menu_kb()
    )


# ==================== HAYDOVCHILARGA XABAR YUBORISH ====================

async def notify_nearby_drivers(order_id: int, order_data: dict) -> bool:
    """Eng yaqin haydovchilarga buyurtma haqida xabar yuborish.
    
    Returns:
        True — haydovchi topildi va xabar yuborildi.
        False — haydovchi topilmadi, buyurtma bekor qilindi.
    """
    drivers = await get_online_drivers()
    nearby = find_nearest_drivers(
        drivers,
        order_data["pickup_lat"],
        order_data["pickup_lng"],
        SEARCH_RADIUS_KM
    )

    if not nearby:
        # Haydovchi topilmadi
        passenger_id = (await get_order(order_id))["passenger_id"]
        await bot.send_message(
            passenger_id,
            "😔 Afsuski, hozirda yaqin atrofda haydovchi topilmadi.\n"
            "Biroz kutib qayta urinib ko'ring.",
            reply_markup=main_menu_kb()
        )
        await cancel_order(order_id)
        return False

    order = await get_order(order_id)
    distance_text = f"{order_data.get('distance', '?')} km" if order_data.get('distance') else "noma'lum"
    price_text = format_price(order_data.get("price", 0))

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    for item in nearby:
        driver = item["driver"]
        driver_dist = item["distance"]
        try:
            await driver_bot.send_message(
                driver["telegram_id"],
                f"🆕 <b>Yangi buyurtma #{order_id}!</b>\n\n"
                f"📍 Yo'lovchigacha: <b>{driver_dist} km</b>\n"
                f"📏 Safar masofasi: <b>{distance_text}</b>\n"
                f"💰 Narx: <b>{price_text}</b>\n\n"
                f"Qabul qilasizmi?",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="✅ Qabul qilish",
                            callback_data=f"accept_{order_id}"
                        )],
                        [InlineKeyboardButton(
                            text="❌ Rad etish",
                            callback_data=f"reject_{order_id}"
                        )]
                    ]
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Haydovchiga xabar yuborishda xato: {e}")

    return True

# ==================== BUYURTMANI BEKOR QILISH ====================

@router.message(OrderState.waiting_driver, F.text == "❌ Buyurtmani bekor qilish")
async def cancel_waiting_order(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    
    if order_id:
        order = await get_order(order_id)
        if order and order["status"] != "searching":
            await state.clear()
            await message.answer(
                "⚠️ Kechirasiz, sizning buyurtmangiz allaqachon haydovchi tomonidan qabul qilingan va u yo'lga chiqqan.\n"
                "Uni bekor qilish uchun haydovchi bilan bog'laning.",
                reply_markup=main_menu_kb()
            )
            return
            
        await cancel_order(order_id)
        
    await state.clear()
    await message.answer(
        "❌ Buyurtma bekor qilindi.\n\n"
        "Asosiy menyu:",
        reply_markup=main_menu_kb()
    )


# ==================== PROFIL ====================

@router.message(F.text == "👤 Mening profilim")
async def my_profile(message: Message):
    passenger = await get_passenger(message.from_user.id)
    if passenger:
        phone = passenger["phone"] or "kiritilmagan"
        await message.answer(
            f"👤 <b>Sizning profilingiz:</b>\n\n"
            f"📛 Ism: {passenger['full_name']}\n"
            f"📱 Telefon: {phone}\n"
            f"📅 Ro'yxatdan o'tgan: {passenger['created_at'][:10]}",
            parse_mode="HTML"
        )
    else:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start buyrug'ini bosing.")


# ==================== TARIX ====================

@router.message(F.text == "📜 Safarlar tarixi")
async def ride_history(message: Message):
    history = await get_passenger_history(message.from_user.id, limit=5)
    if not history:
        await message.answer("📜 Siz hali birorta ham safar qilmagansiz.")
        return

    text = "📜 <b>Oxirgi safarlaringiz:</b>\n\n"
    for h in history:
        status_emoji = "✅" if h["status"] == "completed" else "❌"
        driver_name = h["driver_name"] or "noma'lum"
        price = format_price(h["price"]) if h["price"] else "—"
        date = h["created_at"][:16] if h["created_at"] else "—"
        text += (
            f"{status_emoji} <b>Buyurtma #{h['id']}</b>\n"
            f"   🚗 Haydovchi: {driver_name}\n"
            f"   💰 Narx: {price}\n"
            f"   📅 Sana: {date}\n\n"
        )

    await message.answer(text, parse_mode="HTML")


# ==================== BAHO BERISH ====================

@router.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    order_id = int(parts[1])
    rating_val = parts[2]

    if rating_val == "skip":
        await callback.message.edit_text("⏭ Baho berilmadi. Rahmat!")
        await state.clear()
        return

    rating = int(rating_val)
    order = await get_order(order_id)
    if order and order["driver_id"]:
        await add_review(
            order_id=order_id,
            from_user=callback.from_user.id,
            to_user=order["driver_id"],
            rating=rating
        )

    stars = "⭐" * rating
    await callback.message.edit_text(
        f"Rahmat! Siz {stars} baho berdingiz.\n"
        "Yaxshi safar tilaymiz! 🚖"
    )
    await state.clear()


# ==================== YORDAM ====================

@router.message(F.text == "ℹ️ Yordam")
async def help_cmd(message: Message):
    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "🚖 <b>Taksi chaqirish</b> — joylashuvingizni yuboring va eng yaqin haydovchi topiladi.\n\n"
        "📜 <b>Safarlar tarixi</b> — oldingi safarlaringizni ko'ring.\n\n"
        "👤 <b>Mening profilim</b> — profilingizni ko'ring.\n\n"
        "❓ Savollar bo'lsa: @admin_username",
        parse_mode="HTML"
    )


# ==================== BEKOR QILISH (har qanday holatda) ====================

@router.message(F.text == "❌ Bekor qilish")
async def universal_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Bekor qilindi. Asosiy menyu:",
        reply_markup=main_menu_kb()
    )


# ==================== BOT ISHGA TUSHIRISH ====================

async def main():
    await init_db()
    logger.info("🚖 Yo'lovchi boti ishga tushmoqda...")
    try:
        await dp.start_polling(bot)
    finally:
        # Graceful shutdown — barcha resurslarni to'g'ri yopish
        from shared.utils import close_http_session
        from shared.database import close_pool
        await close_http_session()
        await close_pool()
        await driver_bot.session.close()
        await bot.session.close()
        logger.info("🔒 Yo'lovchi boti to'xtatildi")


if __name__ == "__main__":
    asyncio.run(main())
