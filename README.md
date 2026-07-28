# 🚖 Taxi Bot Loyihasi (Yo'lovchi va Haydovchi)

Ushbu loyiha Telegram platformasida ishlovchi, to'liq funksional taksi xizmatini taqdim etuvchi 2 ta alohida botdan iborat. Botlar zamonaviy Python texnologiyalari yordamida yozilgan va bitta umumiy ma'lumotlar bazasi orqali o'zaro bog'langan.

## 🏗 Loyiha Arxitekturasi va Texnologiyalar

- **Dasturlash tili:** Python 3.14
- **Asosiy kutubxona:** `aiogram 3.15.0` (Telegram bot API bilan ishlash uchun eng zamonaviy asinxron kutubxona)
- **Ma'lumotlar bazasi:** SQLite (`aiosqlite` orqali asinxron ulanish) - Ma'lumotlarni yengil va tez saqlash uchun.
- **Geolokatsiya va masofa:** `geopy` - Haversine formulasi yordamida koordinatalar (kenglik va uzunlik) orqali masofani hisoblash uchun.
- **Konfiguratsiya:** `python-dotenv` - Maxfiy ma'lumotlar (Tokenlar, narxlar) ni `.env` faylida xavfsiz saqlash uchun.

## 📂 Loyiha Strukturasi

```text
BOT_TAKSI/
│
├── .env                    # Bot tokenlari, narxlar va sozlamalar saqlanadigan fayl.
├── requirements.txt        # Loyihaga kerakli Python kutubxonalar ro'yxati.
├── taxi.db                 # SQLite ma'lumotlar bazasi fayli (avtomatik yaratiladi).
├── README.md               # Loyiha haqida ma'lumot (ushbu fayl).
│
├── shared/                 # Ikkala bot uchun umumiy bo'lgan kodlar
│   ├── __init__.py
│   ├── config.py           # .env dan o'zgaruvchilarni o'qib beruvchi modul.
│   ├── database.py         # DB yaratish va barcha SQL so'rovlar (CRUD) yozilgan modul.
│   └── utils.py            # Masofa va narxni hisoblash, yaqin haydovchilarni qidirish funksiyalari.
│
├── BOT_YOLOVCHI/           # Yo'lovchilar uchun bot
│   ├── main.py             # Botning asosiy mantig'i (buyurtma berish, tarix, baholash).
│   └── keyboards.py        # Yo'lovchi botining menyu va tugmalari.
│
└── BOT_HAYDOVCHI/          # Haydovchilar uchun bot
    ├── main.py             # Botning asosiy mantig'i (onlayn bo'lish, buyurtma qabul qilish).
    └── keyboards.py        # Haydovchi botining menyu va tugmalari.
```

## 🛠 Asosiy Funksionallik

### 👤 Yo'lovchi Boti (`@TaxiYolovchi_Bot`)
1. **Ro'yxatdan o'tish:** Kontakt yuborish orqali.
2. **Taksi chaqirish:** 
   - O'z joylashuvini yuboradi.
   - Borish manzilini xaritadan yuboradi yoki "Haydovchiga aytaman" rejimini tanlaydi.
   - Bot masofani va narxni hisoblaydi (`PRICE_PER_KM = 3000 so'm/km`).
3. **Kutish va Haydovchini topish:** Tasdiqlangach, bot atrofdagi onlayn haydovchilarni izlaydi va buyurtmani ularga yuboradi. Haydovchi topilgach, yo'lovchiga haydovchi ma'lumotlari yuboriladi.
4. **Safarlar tarixi va Profil:** O'zining tugallangan safarlarini va profilini ko'rish imkoniyati.
5. **Baholash:** Safar tugagach, haydovchiga 1 dan 5 gacha yulduz bilan baho berish.

### 🚗 Haydovchi Boti (`@TaxiHaydovchi_Bot`)
1. **Ro'yxatdan o'tish:** Ism, raqam, mashina modeli va davlat raqamini kiritish.
2. **Onlayn/Oflayn rejim:** Faqat onlayn va joylashuvini yuborgan haydovchilarga buyurtma keladi.
3. **Buyurtma qabul qilish:** Yo'lovchining masofasi va narxini ko'rgan holda buyurtmani qabul qilish yoki rad etish. Buyurtma qabul qilinganda avtomatik tarzda yo'lovchining joylashuvi xaritada keladi.
4. **Safar jarayoni:** "Yetib keldim/Boshlash" va "Safarni tugatish" tugmalari orqali safarni boshqarish. Yo'lovchining lokatsiyasini qayta so'rab olish imkoniyati.
5. **Statistika:** Bugungi va umumiy qilingan safarlar soni hamda daromadni ko'rish.

## 🗄 Ma'lumotlar Bazasi (Database Schema)

Tizimda 4 ta asosiy jadval mavjud:
1. `passengers`: Yo'lovchi ID, ism, telefon raqam.
2. `drivers`: Haydovchi ID, ism, mashina modeli, onlayn holati, reytingi (1.0 - 5.0 gacha), hozirgi lokatsiyasi (lat, lng).
3. `orders`: Buyurtma tafsilotlari (qayerdan, qayerga, kim buyurtma berdi, qaysi haydovchi oldi, narxi, masofasi va holati - *searching, accepted, riding, completed, cancelled*).
4. `reviews`: Safar yakunlangach berilgan baholar (rating).

## 🚀 Ishga tushirish qoidalari

1. `requirements.txt` dagi kutubxonalarni o'rnatish: `pip install -r requirements.txt`
2. `.env` faylida ikkala bot tokenini kiritish.
3. Yo'lovchi botini ishga tushirish: `python BOT_YOLOVCHI/main.py`
4. Haydovchi botini ishga tushirish: `python BOT_HAYDOVCHI/main.py`

*Loyiha xavfsiz va asinxron tarzda ishlashga to'liq moslashtirilgan.*
