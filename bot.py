#!/usr/bin/env python3
"""
Professional Telegram Bot - Dasturchi xizmatlari uchun
Buyurtma qabul qilish, katalog va admin panel
"""

import logging
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)

# ==================== SOZLAMALAR ====================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")          # @BotFather dan oling
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))                   # Sizning Telegram ID-ingiz


# ==================== XIZMATLAR KATALOGI ====================
SERVICES = {
    "web_landing": {
        "name": "🌐 Landing Page",
        "desc": "Zamonaviy bir sahifali reklama sayti",
        "features": ["Responsive dizayn", "Tez yuklanish", "SEO optimizatsiya", "3 ta sahifa"],
        "price": 500_000,
        "duration": "3-5 kun",
        "emoji": "🌐"
    },
    "web_corporate": {
        "name": "🏢 Korporativ sayt",
        "desc": "Ko'p sahifali biznes sayti",
        "features": ["Admin panel", "Blog tizimi", "Aloqa formasi", "5-10 sahifa"],
        "price": 1_500_000,
        "duration": "7-14 kun",
        "emoji": "🏢"
    },
    "web_ecommerce": {
        "name": "🛒 Internet do'kon",
        "desc": "To'liq savdo platformasi",
        "features": ["Mahsulot katalogi", "Savat & To'lov", "Admin panel", "Hisobotlar"],
        "price": 3_000_000,
        "duration": "14-21 kun",
        "emoji": "🛒"
    },
    "tg_simple": {
        "name": "🤖 Oddiy Telegram Bot",
        "desc": "Ma'lumot beruvchi yoki buyurtma boti",
        "features": ["Inline klaviatura", "Xabar yuborish", "Admin panel", "Statistika"],
        "price": 800_000,
        "duration": "2-4 kun",
        "emoji": "🤖"
    },
    "tg_advanced": {
        "name": "⚡ Murakkab Telegram Bot",
        "desc": "To'lov, CRM, bazali bot",
        "features": ["To'lov tizimi", "Ma'lumotlar bazasi", "CRM", "API integratsiya"],
        "price": 2_000_000,
        "duration": "7-14 kun",
        "emoji": "⚡"
    },
    "fullstack": {
        "name": "🚀 Full-Stack Loyiha",
        "desc": "Sayt + Bot + API + Admin",
        "features": ["Web sayt", "Telegram bot", "REST API", "Admin dashboard"],
        "price": 5_000_000,
        "duration": "21-30 kun",
        "emoji": "🚀"
    }
}

# ==================== CONVERSATION STATES ====================
(MAIN_MENU, CATALOG, SERVICE_DETAIL, ORDER_NAME, ORDER_PHONE,
 ORDER_DESC, ORDER_LINK, ORDER_CONFIRM, ADMIN_MENU) = range(9)

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MA'LUMOTLAR SAQLASH (JSON fayl) ====================
ORDERS_FILE = "orders.json"

def load_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_orders(orders):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

def get_next_order_id():
    orders = load_orders()
    if not orders:
        return "ORD-001"
    # ID ni raqam bo'yicha hisoblash (xavfsiz)
    nums = []
    for k in orders.keys():
        try:
            nums.append(int(k.replace("ORD-", "")))
        except ValueError:
            pass
    next_num = max(nums) + 1 if nums else 1
    return f"ORD-{next_num:03d}"

def get_queue_position(user_id: int):
    """Foydalanuvchining navbat raqami va oldidagi odamlar sonini qaytaradi.
    Return: (order_id, position, ahead_count) yoki (None, None, None)"""
    orders = load_orders()
    # Faqat faol buyurtmalar (yangi yoki qabul qilingan)
    active_statuses = ("yangi", "qabul", "jarayonda")
    # Tartib bo'yicha saralash
    queue = [
        (oid, o) for oid, o in orders.items()
        if o.get("status") in active_statuses
    ]
    # ID raqami bo'yicha tartiblash
    queue.sort(key=lambda x: int(x[0].replace("ORD-", "")))

    user_orders = [(i, oid, o) for i, (oid, o) in enumerate(queue) if o.get("user_id") == user_id]
    if not user_orders:
        return None, None, None

    # Eng yaqin (birinchi) faol buyurtma
    pos_in_queue, order_id, order = user_orders[0]
    ahead = pos_in_queue  # 0-indexed: oldidagi odamlar soni
    position = pos_in_queue + 1  # 1-indexed: navbat raqami
    return order_id, position, ahead

# ==================== YORDAMCHI FUNKSIYALAR ====================
def format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ") + " so'm"

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_CHAT_ID

# ==================== ASOSIY MENYU ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("📋 Xizmatlar katalogi", callback_data="catalog")],
        [InlineKeyboardButton("📝 Buyurtma berish", callback_data="order_start")],
        [InlineKeyboardButton("� Navbatim", callback_data="my_queue")],
        [InlineKeyboardButton("�💬 Aloqa", callback_data="contact")],
        [InlineKeyboardButton("❓ Savollar (FAQ)", callback_data="faq")],
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("👨‍💼 Admin Panel", callback_data="admin")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"👋 Assalomu alaykum, *{user.first_name}*!\n\n"
        "Men — *Dasturchi xizmatlari boti*\n\n"
        "🌐 Web sayt yaratish\n"
        "🤖 Telegram bot ishlab chiqish\n"
        "⚡ Full-stack loyihalar\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=reply_markup, parse_mode="Markdown"
        )
    return MAIN_MENU

# ==================== KATALOG ====================
async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for key, service in SERVICES.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{service['emoji']} {service['name']} — {format_price(service['price'])}",
                callback_data=f"service_{key}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])

    await query.edit_message_text(
        "📋 *Xizmatlar katalogi*\n\n"
        "Batafsil ma'lumot uchun xizmatni tanlang:\n",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return CATALOG

async def show_service_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    service_key = query.data.replace("service_", "")
    service = SERVICES.get(service_key)
    if not service:
        await query.answer("Xizmat topilmadi!")
        return CATALOG

    context.user_data["selected_service"] = service_key

    features_text = "\n".join([f"  ✅ {f}" for f in service["features"]])
    text = (
        f"{service['emoji']} *{service['name']}*\n\n"
        f"📝 {service['desc']}\n\n"
        f"*Nima kiradi:*\n{features_text}\n\n"
        f"💰 *Narx:* {format_price(service['price'])}\n"
        f"⏱ *Muddat:* {service['duration']}\n"
    )

    keyboard = [
        [InlineKeyboardButton("📝 Shu xizmatni buyurtma qilish", callback_data=f"order_{service_key}")],
        [InlineKeyboardButton("🔙 Katalogga qaytish", callback_data="catalog")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return SERVICE_DETAIL

# ==================== BUYURTMA JARAYONI ====================
async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Agar xizmat tanlangan bo'lsa
    if query.data.startswith("order_") and query.data != "order_start":
        service_key = query.data.replace("order_", "")
        context.user_data["order_service"] = service_key
        context.user_data["order"] = {"service": service_key}

    text = (
        "📝 *Buyurtma berish*\n\n"
        "Ismi-sharif yoki kompaniya nomingizni yozing:\n"
        "_Masalan: Alisher Valiyev_"
    )

    keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="back_main")]]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ORDER_NAME

async def get_order_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("❌ Iltimos, to'g'ri ism kiriting!")
        return ORDER_NAME

    context.user_data.setdefault("order", {})["name"] = name

    keyboard = [[KeyboardButton("📞 Raqamni yuborish", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        f"✅ Rahmat, *{name}*!\n\n"
        "📱 Telefon raqamingizni yuboring yoki qo'lda kiriting:\n"
        "_Masalan: +998901234567_",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return ORDER_PHONE

async def get_order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()

    if len(phone) < 9:
        await update.message.reply_text("❌ Noto'g'ri raqam! Qayta kiriting:")
        return ORDER_PHONE

    context.user_data["order"]["phone"] = phone

    from telegram import ReplyKeyboardRemove
    keyboard = [
        [InlineKeyboardButton(s["name"], callback_data=f"cat_{k}")]
        for k, s in SERVICES.items()
    ]
    keyboard.append([InlineKeyboardButton("🔸 Boshqa (o'zim yozaman)", callback_data="cat_custom")])

    await update.message.reply_text(
        "📋 *Qaysi xizmat kerak?*\n\nTanlang yoki o'zingiz yozing:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ORDER_DESC

async def select_service_in_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cat_custom":
        context.user_data["order"]["service_name"] = "Boshqa"
        await query.edit_message_text(
            "✏️ Loyihangiz haqida batafsil yozing:\n\n"
            "_Nima qilmoqchisiz, qanday funksiyalar kerak, misollar va h.k._",
            parse_mode="Markdown"
        )
    else:
        service_key = query.data.replace("cat_", "")
        service = SERVICES.get(service_key, {})
        context.user_data["order"]["service_name"] = service.get("name", "Noma'lum")
        context.user_data["order"]["service_price"] = service.get("price", 0)

        await query.edit_message_text(
            f"✅ *{service.get('name')}* tanlandi!\n\n"
            "✏️ Loyihangiz haqida qo'shimcha ma'lumot yozing:\n"
            "_Maxsus talablar, dizayn fikrlari, misollar..._",
            parse_mode="Markdown"
        )
    return ORDER_DESC

async def get_order_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    context.user_data["order"]["description"] = desc

    keyboard = [
        [InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_link")],
    ]
    await update.message.reply_text(
        "🌐 *Sayt linki yoki Telegram username*\n\n"
        "Agar mavjud sayt yoki ijtimoiy tarmoq sahifangiz bo'lsa yuboring:\n"
        "_Masalan: https://example.uz yoki @username_\n\n"
        "_Agar yo'q bo'lsa \"O'tkazib yuborish\" tugmasini bosing_",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ORDER_LINK

async def get_order_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    context.user_data["order"]["link"] = link
    await show_order_confirm_msg(update.message, context)
    return ORDER_CONFIRM

async def skip_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["order"]["link"] = "-"
    await show_order_confirm(query, context)
    return ORDER_CONFIRM



async def show_order_confirm(query, context):
    order = context.user_data.get("order", {})
    link = order.get('link', '-')
    link_line = f"🌐 *Link/Username:* {link}\n" if link and link != "-" else ""
    text = (
        "📋 *Buyurtmangizni tekshiring:*\n\n"
        f"👤 *Ism:* {order.get('name', '-')}\n"
        f"📱 *Telefon:* {order.get('phone', '-')}\n"
        f"🛠 *Xizmat:* {order.get('service_name', '-')}\n"
        f"{link_line}"
        f"📝 *Tavsif:* {order.get('description', '-')[:100]}...\n\n"
        "✅ Tasdiqlaysizmi?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_yes")],
        [InlineKeyboardButton("✏️ Qayta kiritish", callback_data="order_start")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="back_main")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_order_confirm_msg(message, context):
    order = context.user_data.get("order", {})
    link = order.get('link', '-')
    link_line = f"🌐 *Link/Username:* {link}\n" if link and link != "-" else ""
    text = (
        "📋 *Buyurtmangizni tekshiring:*\n\n"
        f"👤 *Ism:* {order.get('name', '-')}\n"
        f"📱 *Telefon:* {order.get('phone', '-')}\n"
        f"🛠 *Xizmat:* {order.get('service_name', '-')}\n"
        f"{link_line}"
        f"📝 *Tavsif:* {order.get('description', '-')[:100]}\n\n"
        "✅ Tasdiqlaysizmi?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="back_main")],
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order = context.user_data.get("order", {})
    order_id = get_next_order_id()
    order["id"] = order_id
    order["status"] = "yangi"
    order["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    order["user_id"] = update.effective_user.id

    # Saqlash
    orders = load_orders()
    orders[order_id] = order
    save_orders(orders)

    # Adminga xabar
    link = order.get('link', '-')
    link_line = f"🌐 *Link/Username:* {link}\n" if link and link != "-" else ""
    admin_text = (
        f"🆕 *YANGI BUYURTMA* #{order_id}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 *Ism:* {order.get('name')}\n"
        f"📱 *Tel:* {order.get('phone')}\n"
        f"🛠 *Xizmat:* {order.get('service_name')}\n"
        f"{link_line}"
        f"📝 *Tavsif:* {order.get('description')}\n"
        f"🕐 *Vaqt:* {order.get('date')}\n"
        f"━━━━━━━━━━━━━━━"
    )
    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Qabul qilish", callback_data=f"admin_accept_{order_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"admin_reject_{order_id}"),
        ]
    ])

    try:
        await context.bot.send_message(
            ADMIN_CHAT_ID, admin_text,
            reply_markup=admin_keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Admin xabari yuborishda xato: {e}")

    # Navbat hisoblash
    orders_all = load_orders()
    active_statuses = ("yangi", "qabul", "jarayonda")
    queue = [
        oid for oid, o in orders_all.items()
        if o.get("status") in active_statuses
    ]
    queue.sort(key=lambda x: int(x.replace("ORD-", "")))
    try:
        pos = queue.index(order_id) + 1
    except ValueError:
        pos = len(queue)
    ahead = pos - 1

    # Foydalanuvchiga javob — navbat bilan
    if pos == 1:
        queue_msg = "🚀 *Siz navbatda birinchisiz!* Tez orada bog'lanaman."
    else:
        queue_msg = (
            f"🔢 *Navbatingiz:* {pos}-o'rin\n"
            f"👥 Sizdan oldin: *{ahead} ta* mijoz"
        )

    await query.edit_message_text(
        f"🎉 *Buyurtmangiz qabul qilindi!*\n\n"
        f"📌 *Buyurtma raqami:* `{order_id}`\n\n"
        f"{queue_msg}\n\n"
        f"📞 Shoshilinch bo'lsa: @yourusername",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔢 Navbatimni tekshirish", callback_data="my_queue")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_main")]
        ]),
        parse_mode="Markdown"
    )
    return MAIN_MENU

# ==================== ADMIN PANEL ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return MAIN_MENU

    orders = load_orders()
    total = len(orders)
    new_orders = sum(1 for o in orders.values() if o.get("status") == "yangi")
    accepted = sum(1 for o in orders.values() if o.get("status") == "qabul")
    done = sum(1 for o in orders.values() if o.get("status") == "bajarildi")

    keyboard = [
        [InlineKeyboardButton(f"🆕 Yangi buyurtmalar ({new_orders})", callback_data="admin_new")],
        [InlineKeyboardButton(f"📋 Barcha buyurtmalar ({total})", callback_data="admin_all")],
        [InlineKeyboardButton(f"✅ Bajarilganlar ({done})", callback_data="admin_done")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")],
    ]

    await query.edit_message_text(
        f"👨‍💼 *Admin Panel*\n\n"
        f"📊 Jami buyurtmalar: *{total}*\n"
        f"🆕 Yangi: *{new_orders}*\n"
        f"🔄 Jarayonda: *{accepted}*\n"
        f"✅ Bajarildi: *{done}*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ADMIN_MENU

async def admin_show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return MAIN_MENU

    filter_type = query.data.replace("admin_", "")
    orders = load_orders()

    if filter_type == "new":
        filtered = {k: v for k, v in orders.items() if v.get("status") == "yangi"}
        title = "🆕 Yangi buyurtmalar"
    elif filter_type == "done":
        filtered = {k: v for k, v in orders.items() if v.get("status") == "bajarildi"}
        title = "✅ Bajarilgan buyurtmalar"
    else:
        filtered = orders
        title = "📋 Barcha buyurtmalar"

    if not filtered:
        await query.edit_message_text(
            f"{title}\n\n📭 Buyurtmalar yo'q",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin", callback_data="admin")]]),
        )
        return ADMIN_MENU

    keyboard = []
    for order_id, order in list(filtered.items())[-10:]:
        status_emoji = {"yangi": "🆕", "qabul": "🔄", "bajarildi": "✅", "rad": "❌"}.get(order.get("status"), "❓")
        keyboard.append([
            InlineKeyboardButton(
                f"{status_emoji} {order_id} — {order.get('name', '?')} | {order.get('service_name', '?')[:20]}",
                callback_data=f"view_order_{order_id}"
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 Admin panel", callback_data="admin")])

    await query.edit_message_text(
        f"{title}\n_(oxirgi 10 ta)_",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ADMIN_MENU

async def admin_view_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order_id = query.data.replace("view_order_", "")
    orders = load_orders()
    order = orders.get(order_id)

    if not order:
        await query.answer("Buyurtma topilmadi!", show_alert=True)
        return ADMIN_MENU

    status_map = {"yangi": "🆕 Yangi", "qabul": "🔄 Jarayonda", "bajarildi": "✅ Bajarildi", "rad": "❌ Rad etildi"}
    status = status_map.get(order.get("status"), "❓")

    link = order.get('link', '-')
    link_line = f"🌐 *Link/Username:* {link}\n" if link and link != "-" else ""
    text = (
        f"📋 *Buyurtma {order_id}*\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 *Ism:* {order.get('name')}\n"
        f"📱 *Tel:* {order.get('phone')}\n"
        f"🛠 *Xizmat:* {order.get('service_name')}\n"
        f"{link_line}"
        f"📝 *Tavsif:* {order.get('description')}\n"
        f"🕐 *Vaqt:* {order.get('date')}\n"
        f"📌 *Holat:* {status}"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Qabul", callback_data=f"admin_accept_{order_id}"),
            InlineKeyboardButton("🔄 Jarayonda", callback_data=f"admin_process_{order_id}"),
        ],
        [
            InlineKeyboardButton("✅ Bajarildi", callback_data=f"admin_done_{order_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"admin_reject_{order_id}"),
        ],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_all")],
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ADMIN_MENU

async def admin_change_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[1]  # accept / process / done / reject
    order_id = "_".join(parts[2:])

    orders = load_orders()
    if order_id not in orders:
        await query.answer("Buyurtma topilmadi!", show_alert=True)
        return ADMIN_MENU

    status_map = {
        "accept": ("qabul", "✅ Qabul qilindi", "✅ Buyurtmangiz qabul qilindi! Tez orada bog'lanaman."),
        "process": ("jarayonda", "🔄 Jarayonga olindi", "🔄 Loyihangiz ustida ish boshlandi!"),
        "done": ("bajarildi", "✅ Bajarildi deb belgilandi", "🎉 Loyihangiz tayyor! Natijani topshiraman."),
        "reject": ("rad", "❌ Rad etildi", "❌ Afsuski, hozircha bu buyurtmani qabul qila olmayman. Iltimos, boshqa vaqt murojaat qiling."),
    }

    new_status, admin_msg, user_msg = status_map.get(action, ("yangi", "O'zgartirildi", ""))
    orders[order_id]["status"] = new_status
    save_orders(orders)

    # Foydalanuvchiga xabar
    user_id = orders[order_id].get("user_id")
    if user_id and user_msg:
        try:
            await context.bot.send_message(
                user_id,
                f"📌 *Buyurtma #{order_id}*\n\n{user_msg}",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # Agar bajarildi yoki rad etildi — keyingi navbatdagiga xabar
    if new_status in ("bajarildi", "rad"):
        orders_fresh = load_orders()
        active_statuses = ("yangi", "qabul", "jarayonda")
        queue = [
            (oid, o) for oid, o in orders_fresh.items()
            if o.get("status") in active_statuses
        ]
        queue.sort(key=lambda x: int(x[0].replace("ORD-", "")))
        # 1-navbatdagiga (birinchi faol buyurtma sohibi) xabar
        if queue:
            next_oid, next_order = queue[0]
            next_user = next_order.get("user_id")
            if next_user:
                try:
                    await context.bot.send_message(
                        next_user,
                        f"🔔 *Xabar!*\n\nSizdan oldingi buyurtma tugatildi.\n"
                        f"Siz endi *navbatda birinchisiz!* 🚀\n"
                        f"Buyurtma: `{next_oid}`",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

    await query.answer(admin_msg, show_alert=True)
    return ADMIN_MENU

# ==================== STATISTIKA ====================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    orders = load_orders()
    total = len(orders)

    service_count = {}
    for order in orders.values():
        sname = order.get("service_name", "Boshqa")
        service_count[sname] = service_count.get(sname, 0) + 1

    stats_text = "📊 *Statistika*\n\n"
    stats_text += f"📦 Jami buyurtmalar: *{total}*\n\n"
    stats_text += "*Xizmatlar bo'yicha:*\n"
    for sname, count in sorted(service_count.items(), key=lambda x: -x[1]):
        stats_text += f"  • {sname}: *{count}*\n"

    await query.edit_message_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin", callback_data="admin")]]),
        parse_mode="Markdown"
    )
    return ADMIN_MENU

# ==================== ALOQA VA FAQ ====================
async def show_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📞 *Aloqa*\n\n"
        "💬 Telegram: @yourusername\n"
        "📱 Telefon: +998 90 123 45 67\n"
        "📧 Email: you@email.com\n"
        "🌐 Sayt: yourwebsite.uz\n\n"
        "🕐 Ish vaqti: 9:00 - 22:00",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Bosh menyu", callback_data="back_main")]]),
        parse_mode="Markdown"
    )
    return MAIN_MENU

async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "❓ *Tez-tez so'raladigan savollar*\n\n"
        "❓ *Qancha vaqtda sayt tayyor bo'ladi?*\n"
        "✅ Landing page 3-5 kun, korporativ 7-14 kun.\n\n"
        "❓ *Saytga kafolat bormi?*\n"
        "✅ Ha, 3 oy bepul texnik yordam.\n\n"
        "❓ *Dizaynni o'zim bersa bo'ladimi?*\n"
        "✅ Albatta! Figma/XD yoki rasm formatida.\n\n"
        "❓ *Narxni kamaytirib bo'ladimi?*\n"
        "✅ Talabga qarab muhokama qilamiz.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Bosh menyu", callback_data="back_main")]]),
        parse_mode="Markdown"
    )
    return MAIN_MENU

# ==================== NAVBAT KOMANDASI ====================
async def my_queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi o'z navbatini tekshiradi (/navbat yoki inline tugma)"""
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        send = update.callback_query.edit_message_text
        await update.callback_query.answer()
    else:
        user_id = update.effective_user.id
        send = update.message.reply_text

    order_id, position, ahead = get_queue_position(user_id)

    if order_id is None:
        text = (
            "🔢 *Navbatingiz*\n\n"
            "❌ Sizda hozirda faol buyurtma yo'q.\n"
            "Yangi buyurtma berish uchun *Buyurtma berish* tugmasini bosing."
        )
    elif position == 1:
        text = (
            f"🔢 *Navbatingiz*\n\n"
            f"📌 Buyurtma: `{order_id}`\n"
            f"🚀 *Siz navbatda birinchisiz!*\n"
            f"Tez orada siz bilan bog'lanaman."
        )
    else:
        text = (
            f"🔢 *Navbatingiz*\n\n"
            f"📌 Buyurtma: `{order_id}`\n"
            f"🔢 Navbat raqamingiz: *{position}-o'rin*\n"
            f"👥 Sizdan oldin: *{ahead} ta* mijoz\n\n"
            f"⏳ Navbat kelganda xabar beramiz!"
        )

    await send(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Bosh menyu", callback_data="back_main")]
        ])
    )
    return MAIN_MENU

# ==================== CALLBACK HANDLER ====================
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "back_main":
        return await start(update, context)
    elif query.data == "my_queue":
        return await my_queue_command(update, context)
    elif query.data == "catalog":
        return await show_catalog(update, context)
    elif query.data.startswith("service_"):
        return await show_service_detail(update, context)
    elif query.data == "contact":
        return await show_contact(update, context)
    elif query.data == "faq":
        return await show_faq(update, context)
    elif query.data == "admin":
        return await admin_panel(update, context)
    elif query.data in ("admin_new", "admin_all", "admin_done"):
        return await admin_show_orders(update, context)
    elif query.data == "admin_stats":
        return await admin_stats(update, context)
    elif query.data.startswith("view_order_"):
        return await admin_view_order(update, context)
    elif query.data.startswith("admin_accept_") or query.data.startswith("admin_reject_") \
            or query.data.startswith("admin_process_") or query.data.startswith("admin_done_"):
        return await admin_change_status(update, context)
    elif query.data in ("order_start",) or query.data.startswith("order_"):
        return await order_start(update, context)
    elif query.data.startswith("cat_"):
        return await select_service_in_order(update, context)
    elif query.data == "skip_link":
        return await skip_link(update, context)
    elif query.data == "confirm_yes":
        return await confirm_order(update, context)

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(handle_callbacks)],
            CATALOG: [CallbackQueryHandler(handle_callbacks)],
            SERVICE_DETAIL: [CallbackQueryHandler(handle_callbacks)],
            ORDER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_order_name),
                CallbackQueryHandler(handle_callbacks),
            ],
            ORDER_PHONE: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), get_order_phone),
                CallbackQueryHandler(handle_callbacks),
            ],
            ORDER_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_order_desc),
                CallbackQueryHandler(handle_callbacks),
            ],
            ORDER_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_order_link),
                CallbackQueryHandler(handle_callbacks),
            ],
            ORDER_CONFIRM: [CallbackQueryHandler(handle_callbacks)],
            ADMIN_MENU: [CallbackQueryHandler(handle_callbacks)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("navbat", my_queue_command))

    print("🤖 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
