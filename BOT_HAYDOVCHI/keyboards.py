from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def main_menu_online_kb():
    """Asosiy menyu (onlayn rejimda)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔴 Oflayn bo'lish")],
            [KeyboardButton(text="📍 Joylashuvni yangilash", request_location=True)],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📜 Safarlar tarixi")],
            [KeyboardButton(text="👤 Mening profilim")]
        ],
        resize_keyboard=True
    )


def main_menu_offline_kb():
    """Asosiy menyu (oflayn rejimda)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 Onlayn bo'lish")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📜 Safarlar tarixi")],
            [KeyboardButton(text="👤 Mening profilim")]
        ],
        resize_keyboard=True
    )


def registration_phone_kb():
    """Telefon raqamini yuborish (ro'yxatdan o'tish)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def active_ride_kb():
    """Faol safar tugmalari."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Yetib keldim — safarni boshlash")],
            [KeyboardButton(text="🏁 Safarni tugatish")],
            [KeyboardButton(text="📍 Yo'lovchi lokatsiyasi")],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True
    )


def location_kb():
    """Joylashuvni yuborish."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
