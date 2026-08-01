import sys
import os
import asyncio
import logging

# Loyiha root papkasini Python path ga qo'shish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder

from shared.config import DRIVER_BOT_TOKEN, PASSENGER_BOT_TOKEN, ADMIN_ID, REDIS_URL
from shared.database import (
    init_db, register_driver, get_driver, set_driver_online,
    update_driver_location, get_order, accept_order, start_ride,
    complete_order, cancel_order, get_active_order_by_driver,
    get_driver_history, get_driver_stats, approve_driver,
    update_order_price, get_system_stats, reject_driver, get_all_users,
    cleanup_zombie_orders
)
from shared.utils import format_price
from keyboards import (
    main_menu_online_kb, main_menu_offline_kb, registration_phone_kb,
    active_ride_kb, location_kb
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot va Dispatcher (RedisStorage — bot restart bo'lganda state saqlanadi)
bot = Bot(token=DRIVER_BOT_TOKEN)
storage = RedisStorage.from_url(REDIS_URL, key_builder=DefaultKeyBuilder(prefix="driver"))
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Yo'lovchi botiga xabar yuborish uchun
passenger_bot = Bot(token=PASSENGER_BOT_TOKEN)


# ==================== HOLATLAR (States) ====================

class Registration(StatesGroup):
    phone = State()
    car_model = State()
    car_number = State()


class DriverState(StatesGroup):
    online = State()
    riding = State()
    waiting_for_price = State()

class AdminState(StatesGroup):
    broadcast = State()


# ==================== /start KOMANDASI ====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    driver = await get_driver(message.from_user.id)

    if driver:
        if driver["is_approved"]:
            is_online = driver["is_online"]
            kb = main_menu_online_kb() if is_online else main_menu_offline_kb()
            status = "🟢 Onlayn" if is_online else "🔴 Oflayn"
            await message.answer(
                f"🚗 Xush kelibsiz, {driver['full_name']}!\n"
                f"Holatangiz: {status}",
                reply_markup=kb
            )
        else:
            await message.answer(
                "⏳ Sizning arizangiz hali admin tomonidan tasdiqlanmagan.\n"
                "Iltimos, kuting. Tasdiqlanganingizda xabar beramiz."
            )
    else:
        await message.answer(
            "👋 <b>Haydovchi botiga xush kelibsiz!</b>\n\n"
            "Ro'yxatdan o'tish uchun telefon raqamingizni yuboring:",
            reply_markup=registration_phone_kb(),
            parse_mode="HTML"
        )
        await state.set_state(Registration.phone)


# ==================== RO'YXATDAN O'TISH ====================

@router.message(Registration.phone, F.contact)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer(
        "🚗 Mashina modelini kiriting:\n"
        "Masalan: <b>Cobalt</b>, <b>Nexia 3</b>, <b>Spark</b>",
        parse_mode="HTML"
    )
    await state.set_state(Registration.car_model)


@router.message(Registration.car_model, F.text)
async def process_car_model(message: Message, state: FSMContext):
    await state.update_data(car_model=message.text)
    await message.answer(
        "🔢 Mashina raqamini kiriting:\n"
        "Masalan: <b>01 A 123 AA</b>",
        parse_mode="HTML"
    )
    await state.set_state(Registration.car_number)


@router.message(Registration.car_number, F.text)
async def process_car_number(message: Message, state: FSMContext):
    data = await state.get_data()
    await register_driver(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        phone=data["phone"],
        car_model=data["car_model"],
        car_number=message.text.upper()
    )
    
    # Adminga yuborish
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_approve_{message.from_user.id}")],
        [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"admin_reject_{message.from_user.id}")]
    ])
    
    if ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🆕 <b>Yangi haydovchi ro'yxatdan o'tdi!</b>\n\n"
                f"👤 Ism: {message.from_user.full_name}\n"
                f"📱 Telefon: {data['phone']}\n"
                f"🚗 Mashina: {data['car_model']}\n"
                f"🔢 Raqam: {message.text.upper()}\n\n"
                f"Tasdiqlaysizmi?",
                reply_markup=admin_kb,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Adminga yuborishda xato: {e}")

    await state.clear()
    await message.answer(
        "✅ <b>Arizangiz qabul qilindi!</b>\n\n"
        "Ayni paytda arizangiz adminga tekshirish uchun yuborildi.\n"
        "Tasdiqlangach sizga xabar beramiz.",
        reply_markup=main_menu_offline_kb(),
        parse_mode="HTML"
    )


# ==================== ONLAYN / OFLAYN ====================

@router.message(F.text == "🟢 Onlayn bo'lish")
async def go_online(message: Message, state: FSMContext):
    driver = await get_driver(message.from_user.id)
    if not driver:
        await message.answer("Avval ro'yxatdan o'ting: /start")
        return
    if not driver["is_approved"]:
        await message.answer("⏳ Arizangiz hali tasdiqlanmagan.")
        return

    await set_driver_online(message.from_user.id, True)
    await state.set_state(DriverState.online)
    await message.answer(
        "🟢 <b>Siz onlaynsiz!</b>\n\n"
        "📍 Joylashuvingizni yuboring, shunda sizga buyurtma keladi.\n"
        "Joylashuvni vaqti-vaqti bilan yangilab turing.",
        reply_markup=main_menu_online_kb(),
        parse_mode="HTML"
    )


@router.message(F.text == "🔴 Oflayn bo'lish")
async def go_offline(message: Message, state: FSMContext):
    await set_driver_online(message.from_user.id, False)
    await state.clear()
    await message.answer(
        "🔴 <b>Siz oflayn bo'ldingiz.</b>\n\n"
        "Buyurtmalar sizga kelmaydi.",
        reply_markup=main_menu_offline_kb(),
        parse_mode="HTML"
    )


# ==================== JOYLASHUVNI YANGILASH ====================

@router.message(F.location, StateFilter(None, DriverState.online, DriverState.riding))
async def handle_location(message: Message, state: FSMContext):
    await update_driver_location(
        message.from_user.id,
        message.location.latitude,
        message.location.longitude
    )
    
    # Agar bu Live Location bo'lsa
    if message.location.live_period:
        data = await state.get_data()
        if not data.get("live_location_notified"):
            await state.update_data(live_location_notified=True)
            await message.answer(
                "📍 <b>Live Location</b> (Jonli joylashuv) qabul qilindi!\n"
                "Endi sizning harakatingiz avtomatik kuzatib boriladi.",
                parse_mode="HTML"
            )
    else:
        # Oddiy lokatsiya uchun ham har safar javob bermaslik mumkin,
        # yoki xohlasangiz buni ham shunday cheklash mumkin. Hozircha oddiy lokatsiyani qoldiramiz.
        await message.answer(
            "📍 Joylashuvingiz yangilandi!\n"
            f"🗺 {message.location.latitude:.4f}, {message.location.longitude:.4f}"
        )

@router.edited_message(F.location)
async def handle_live_location(message: Message):
    # Jonli joylashuv har gal o'zgarganda bu yerga keladi (bazani avtomat yangilaydi)
    await update_driver_location(
        message.from_user.id,
        message.location.latitude,
        message.location.longitude
    )


# ==================== BUYURTMANI QABUL QILISH ====================

@router.callback_query(F.data.startswith("accept_"))
async def accept_order_handler(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[1])

    # Avval boshqa faol buyurtma bor-yo'qligini tekshiramiz
    active = await get_active_order_by_driver(callback.from_user.id)
    if active:
        await callback.answer("⚠️ Sizda faol buyurtma bor!", show_alert=True)
        return

    success = await accept_order(order_id, callback.from_user.id)
    if not success:
        await callback.answer(
            "❌ Bu buyurtma allaqachon boshqa haydovchi tomonidan qabul qilingan.",
            show_alert=True
        )
        await callback.message.edit_text("❌ Bu buyurtma boshqa haydovchi tomonidan olingan.")
        return

    order = await get_order(order_id)
    driver = await get_driver(callback.from_user.id)
    await state.set_state(DriverState.riding)
    await state.update_data(order_id=order_id)

    await callback.message.edit_text(
        f"✅ <b>Buyurtma #{order_id} qabul qildingiz!</b>\n\n"
        f"📍 Yo'lovchi joylashuvi yuboriladi.\n"
        f"Yo'lovchiga yetib borib, 'Yetib keldim' tugmasini bosing.",
        parse_mode="HTML"
    )

    # Yo'lovchiga joylashuv va haydovchi ma'lumotlarini yuborish
    await callback.message.answer(
        "🗺 Yo'lovchiga yetib boring:",
        reply_markup=active_ride_kb()
    )

    # Yo'lovchiga haydovchi topilganini xabar berish
    try:
        from BOT_YOLOVCHI.keyboards import cancel_order_kb
        await passenger_bot.send_message(
            order["passenger_id"],
            f"🎉 <b>Haydovchi topildi!</b>\n\n"
            f"👤 Ism: {driver['full_name']}\n"
            f"🚗 Mashina: {driver['car_model']}\n"
            f"🔢 Raqam: {driver['car_number']}\n"
            f"📞 Telefon: {driver['phone']}\n"
            f"⭐ Reyting: {driver['rating']}/5\n\n"
            f"Haydovchi siz tomonga yo'l oldi.",
            reply_markup=cancel_order_kb(),
            parse_mode="HTML"
        )
        # Yo'lovchiga haydovchining joylashuvini yuborish
        if driver["latitude"] and driver["longitude"]:
            await passenger_bot.send_location(
                order["passenger_id"],
                latitude=driver["latitude"],
                longitude=driver["longitude"]
            )
    except Exception as e:
        logger.error(f"Yo'lovchiga xabar yuborishda xato: {e}")

    await callback.answer("✅ Buyurtma qabul qilindi!")


@router.callback_query(F.data.startswith("reject_"))
async def reject_order_handler(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(f"❌ Buyurtma #{order_id} rad etildi.")
    await callback.answer("Rad etildi")


# ==================== SAFAR BOSHQARUVI ====================

@router.message(F.text == "✅ Yetib keldim — safarni boshlash")
async def arrived_start_ride(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer("⚠️ Faol buyurtma topilmadi.")
        return

    await start_ride(order_id)
    order = await get_order(order_id)

    await message.answer(
        f"🚗 <b>Safar boshlandi!</b>\n\n"
        f"Yo'lovchini manzilga olib boring.\n"
        f"Yetganingizda '🏁 Safarni tugatish' tugmasini bosing.",
        reply_markup=active_ride_kb(),
        parse_mode="HTML"
    )

    # Yo'lovchiga xabar
    try:
        await passenger_bot.send_message(
            order["passenger_id"],
            "🚗 <b>Safar boshlandi!</b>\n"
            "Yaxshi yo'l! 🛣",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Xato: {e}")


@router.message(F.text == "🏁 Safarni tugatish")
async def finish_ride(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer("⚠️ Faol buyurtma topilmadi.")
        return

    order = await get_order(order_id)
    
    # Agar manzil belgilanmagan bo'lsa (Haydovchiga aytaman rejimi), narx kiritishni so'raymiz
    if order["distance_km"] is None:
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        await state.set_state(DriverState.waiting_for_price)
        await message.answer(
            "💰 <b>Manzil oldindan kiritilmagan edi.</b>\n\n"
            "Mijoz jami qancha to'ladi? Summani raqamlarda kiriting (masalan: 15000):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )
        return

    await complete_order(order_id)
    await state.clear()

    price_text = format_price(order["price"]) if order["price"] else "kelishilgan narx"

    await message.answer(
        f"🏁 <b>Safar tugatildi!</b>\n\n"
        f"📦 Buyurtma #{order_id}\n"
        f"💰 Narx: {price_text}\n\n"
        f"Rahmat! Yaxshi ish! 👍",
        reply_markup=main_menu_online_kb(),
        parse_mode="HTML"
    )

    # Yo'lovchiga safar tugaganini xabar berish + baho so'rash
    try:
        from BOT_YOLOVCHI.keyboards import rating_kb
        await passenger_bot.send_message(
            order["passenger_id"],
            f"🏁 <b>Safar tugatildi!</b>\n\n"
            f"💰 To'lov: {price_text}\n\n"
            f"Haydovchiga baho bering:",
            reply_markup=rating_kb(order_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Xato: {e}")


@router.message(DriverState.waiting_for_price, F.text)
async def handle_manual_price(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        # Narx kiritishni bekor qilsa nima bo'ladi? Orqaga qaytamiz
        await state.set_state(DriverState.riding)
        await message.answer("Narx kiritish bekor qilindi.", reply_markup=active_ride_kb())
        return

    try:
        price = int(message.text.replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("⚠️ Iltimos, narxni faqat raqamlarda kiriting (masalan: 15000).")
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await state.clear()
        await message.answer("⚠️ Faol buyurtma topilmadi.", reply_markup=main_menu_online_kb())
        return

    # Narxni bazaga saqlaymiz
    await update_order_price(order_id, price)
    await complete_order(order_id)
    await state.clear()

    order = await get_order(order_id)
    price_text = format_price(price)

    await message.answer(
        f"🏁 <b>Safar tugatildi!</b>\n\n"
        f"📦 Buyurtma #{order_id}\n"
        f"💰 Narx: {price_text}\n\n"
        f"Rahmat! Yaxshi ish! 👍",
        reply_markup=main_menu_online_kb(),
        parse_mode="HTML"
    )

    # Yo'lovchiga xabar
    try:
        from BOT_YOLOVCHI.keyboards import rating_kb
        await passenger_bot.send_message(
            order["passenger_id"],
            f"🏁 <b>Safar tugatildi!</b>\n\n"
            f"💰 To'lov: {price_text}\n\n"
            f"Haydovchiga baho bering:",
            reply_markup=rating_kb(order_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Xato: {e}")


@router.message(F.text == "📍 Yo'lovchi lokatsiyasi")
async def send_passenger_location(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer("⚠️ Faol buyurtma topilmadi.")
        return

    order = await get_order(order_id)
    if order and order["pickup_lat"] and order["pickup_lng"]:
        await message.answer_location(
            latitude=order["pickup_lat"],
            longitude=order["pickup_lng"]
        )
    else:
        await message.answer("📍 Yo'lovchi joylashuvi mavjud emas.")


@router.message(DriverState.riding, F.text == "❌ Bekor qilish")
async def cancel_ride(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    if order_id:
        order = await get_order(order_id)
        await cancel_order(order_id)
        # Yo'lovchiga xabar
        try:
            await passenger_bot.send_message(
                order["passenger_id"],
                "❌ Haydovchi safarni bekor qildi.\n"
                "Iltimos, qayta buyurtma bering.",
            )
        except Exception as e:
            logger.error(f"Xato: {e}")

    await state.clear()
    await message.answer(
        "❌ Safar bekor qilindi.",
        reply_markup=main_menu_online_kb()
    )


# ==================== STATISTIKA ====================

@router.message(F.text == "📊 Statistika")
async def statistics(message: Message):
    stats = await get_driver_stats(message.from_user.id)
    driver = await get_driver(message.from_user.id)

    rating = driver["rating"] if driver else 5.0
    await message.answer(
        f"📊 <b>Sizning statistikangiz:</b>\n\n"
        f"<b>📅 Bugun:</b>\n"
        f"   🚗 Safarlar: {stats['today_rides']}\n"
        f"   💰 Daromad: {format_price(stats['today_income'])}\n\n"
        f"<b>📈 Jami:</b>\n"
        f"   🚗 Safarlar: {stats['total_rides']}\n"
        f"   💰 Daromad: {format_price(stats['total_income'])}\n"
        f"   ⭐ Reyting: {rating}/5",
        parse_mode="HTML"
    )


# ==================== PROFIL ====================

@router.message(F.text == "👤 Mening profilim")
async def my_profile(message: Message):
    driver = await get_driver(message.from_user.id)
    if driver:
        status = "✅ Tasdiqlangan" if driver["is_approved"] else "⏳ Kutilmoqda"
        online = "🟢 Onlayn" if driver["is_online"] else "🔴 Oflayn"
        await message.answer(
            f"👤 <b>Sizning profilingiz:</b>\n\n"
            f"📛 Ism: {driver['full_name']}\n"
            f"📱 Telefon: {driver['phone']}\n"
            f"🚗 Mashina: {driver['car_model']}\n"
            f"🔢 Raqam: {driver['car_number']}\n"
            f"⭐ Reyting: {driver['rating']}/5\n"
            f"🚗 Jami safarlar: {driver['total_rides']}\n"
            f"📋 Holat: {status}\n"
            f"📶 Rejim: {online}",
            parse_mode="HTML"
        )
    else:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start buyrug'ini bosing.")


# ==================== TARIX ====================

@router.message(F.text == "📜 Safarlar tarixi")
async def ride_history(message: Message):
    history = await get_driver_history(message.from_user.id, limit=5)
    if not history:
        await message.answer("📜 Siz hali birorta ham safar qilmagansiz.")
        return

    text = "📜 <b>Oxirgi safarlaringiz:</b>\n\n"
    for h in history:
        status_emoji = "✅" if h["status"] == "completed" else "❌"
        price = format_price(h["price"]) if h["price"] else "—"
        date = h["created_at"][:16] if h["created_at"] else "—"
        text += (
            f"{status_emoji} <b>Buyurtma #{h['id']}</b>\n"
            f"   💰 Narx: {price}\n"
            f"   📅 Sana: {date}\n\n"
        )

    await message.answer(text, parse_mode="HTML")


# ==================== ADMIN PANEL ====================

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    stats = await get_system_stats()
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    admin_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📢 Hammaga xabar yuborish")],
            [KeyboardButton(text="⬅️ Asosiy menyu")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        f"👑 <b>Admin Panel</b>\n\n"
        f"👥 Yo'lovchilar: {stats['passengers']}\n"
        f"🚗 Haydovchilar: {stats['drivers']}\n"
        f"📦 Jami buyurtmalar: {stats['orders_total']}\n"
        f"📅 Bugungi buyurtmalar: {stats['orders_today']}",
        reply_markup=admin_menu,
        parse_mode="HTML"
    )

@router.message(F.text == "⬅️ Asosiy menyu")
async def back_to_main(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await cmd_start(message, state)

@router.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    driver_id = int(callback.data.split("_")[2])
    
    await approve_driver(driver_id)
    await callback.message.edit_text(f"✅ Haydovchi {driver_id} tasdiqlandi!")
    
    try:
        await bot.send_message(
            driver_id,
            "🎉 <b>Tabriklaymiz!</b> Sizning arizangiz tasdiqlandi.\n\n"
            "Endi siz '🟢 Onlayn bo'lish' orqali buyurtmalarni qabul qilishingiz mumkin.",
            reply_markup=main_menu_offline_kb(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Haydovchiga yuborishda xato: {e}")

@router.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    driver_id = int(callback.data.split("_")[2])
    
    await reject_driver(driver_id)
    await callback.message.edit_text(f"❌ Haydovchi {driver_id} rad etildi!")
    
    try:
        await bot.send_message(
            driver_id,
            "❌ Afsuski, sizning arizangiz ma'muriyat tomonidan rad etildi."
        )
    except Exception:
        pass


@router.message(F.text == "📢 Hammaga xabar yuborish")
async def start_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Asosiy menyu")]],
        resize_keyboard=True
    )
    
    await message.answer(
        "📝 Ommaviy xabar matnini yuboring.\n"
        "(Rasm yoki video ham yuborishingiz mumkin)",
        reply_markup=cancel_kb
    )
    await state.set_state(AdminState.broadcast)

@router.message(AdminState.broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if message.text == "⬅️ Asosiy menyu":
        await back_to_main(message, state)
        return
        
    users = await get_all_users()
    sent = 0
    await message.answer("⏳ Xabar yuborilmoqda, kuting...")
    
    for u in users:
        try:
            try:
                await bot.copy_message(chat_id=u, from_chat_id=message.chat.id, message_id=message.message_id)
            except Exception:
                await passenger_bot.copy_message(chat_id=u, from_chat_id=message.chat.id, message_id=message.message_id)
            sent += 1
            await asyncio.sleep(0.05) # Telegram limitlariga tushmaslik uchun
        except Exception:
            pass
            
    await state.clear()
    await message.answer(f"✅ Xabar muvaffaqiyatli {sent} ta foydalanuvchiga yuborildi!")
    await admin_panel(message)


# ==================== ZOMBIE TOZALASH TAYMER ====================

async def zombie_cleanup_loop():
    """Har 30 daqiqada osilib qolgan buyurtmalarni tozalash."""
    while True:
        await asyncio.sleep(30 * 60)  # 30 daqiqa
        try:
            zombies = await cleanup_zombie_orders(max_age_minutes=120)
            if zombies:
                logger.warning(f"🧹 {len(zombies)} ta zombie buyurtma bekor qilindi: {[z['id'] for z in zombies]}")
                # Yo'lovchilarga xabar yuborish
                for z in zombies:
                    try:
                        await passenger_bot.send_message(
                            z["passenger_id"],
                            "⏳ Sizning buyurtmangiz uzoq vaqt javobsiz qoldi.\n"
                            "Buyurtma avtomatik bekor qilindi.\n"
                            "Iltimos, qayta buyurtma bering."
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Zombie tozalashda xato: {e}")


# ==================== BOT ISHGA TUSHIRISH ====================

async def main():
    await init_db()
    # Ishga tushganda darhol tozalash
    zombies = await cleanup_zombie_orders(max_age_minutes=120)
    if zombies:
        logger.warning(f"🧹 Startup: {len(zombies)} ta zombie buyurtma tozalandi")
    # Fonda zombie tozalash taymerini ishga tushirish
    asyncio.create_task(zombie_cleanup_loop())
    logger.info("🚗 Haydovchi boti ishga tushmoqda...")
    try:
        await dp.start_polling(bot)
    finally:
        # Graceful shutdown — barcha resurslarni to'g'ri yopish
        from shared.utils import close_http_session
        from shared.database import close_pool
        await close_http_session()
        await close_pool()
        await passenger_bot.session.close()
        await bot.session.close()
        logger.info("🔒 Haydovchi boti to'xtatildi")


if __name__ == "__main__":
    asyncio.run(main())
