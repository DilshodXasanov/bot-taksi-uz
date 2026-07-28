from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def main_menu_kb():
    """Asosiy menyu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚖 Taksi chaqirish")],
            [KeyboardButton(text="📜 Safarlar tarixi"), KeyboardButton(text="👤 Mening profilim")],
            [KeyboardButton(text="ℹ️ Yordam")]
        ],
        resize_keyboard=True
    )


def phone_kb():
    """Telefon raqamini yuborish."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def location_kb(text="📍 Joylashuvni yuborish"):
    """Joylashuvni yuborish."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text, request_location=True)],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def confirm_order_kb(price: str, distance: str):
    """Buyurtmani tasdiqlash."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Tasdiqlash ({price})", callback_data="confirm_order")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_order")]
        ]
    )


def cancel_order_kb():
    """Buyurtmani bekor qilish (kutish vaqtida)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Buyurtmani bekor qilish")]
        ],
        resize_keyboard=True
    )


def rating_kb(order_id: int):
    """Haydovchiga baho berish."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐1", callback_data=f"rate_{order_id}_1"),
                InlineKeyboardButton(text="⭐2", callback_data=f"rate_{order_id}_2"),
                InlineKeyboardButton(text="⭐3", callback_data=f"rate_{order_id}_3"),
                InlineKeyboardButton(text="⭐4", callback_data=f"rate_{order_id}_4"),
                InlineKeyboardButton(text="⭐5", callback_data=f"rate_{order_id}_5"),
            ],
            [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"rate_{order_id}_skip")]
        ]
    )


def skip_dest_kb():
    """Manzilni o'tkazib yuborish (haydovchiga aytaman)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🗣 Haydovchiga aytaman", 
                callback_data="skip_destination"
            )]
        ]
    )
