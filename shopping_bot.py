import os
import json
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)

# ====== Настройки ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = [431417737, 1117100895]  # вы оба

DATA_FILE = "shopping_data.json"

# ====== Работа с данными ======
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# ====== Утилиты ======
def get_keyboard_main():
    keyboard = [
        [InlineKeyboardButton("🛍️ Список", callback_data="view_list")],
        [InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category")],
        [InlineKeyboardButton("🧹 Очистить всё", callback_data="clear_all")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_keyboard_categories():
    keyboard = []
    for cat, info in data.items():
        emoji = info.get("emoji", "")
        keyboard.append([InlineKeyboardButton(f"{emoji} {cat}", callback_data=f"open_{cat}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_keyboard_items(category):
    keyboard = []
    for item, bought in data[category]["items"].items():
        mark = "✅" if bought else "🛒"
        keyboard.append([
            InlineKeyboardButton(f"{mark} {item}", callback_data=f"toggle_{category}_{item}")
        ])
    keyboard.append([
        InlineKeyboardButton("➕ Добавить товар", callback_data=f"add_item_{category}"),
        InlineKeyboardButton("🗑 Удалить категорию", callback_data=f"delete_category_{category}")
    ])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="view_list")])
    return InlineKeyboardMarkup(keyboard)

# ====== Основные команды ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return
    await update.message.reply_text(
        "👋 Привет! Это ваш общий список покупок.\nВыберите действие:",
        reply_markup=get_keyboard_main()
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in ALLOWED_USERS:
        await query.edit_message_text("⛔ Нет доступа.")
        return

    data_text = query.data

    # Главное меню
    if data_text == "main_menu":
        await query.edit_message_text("🏠 Главное меню", reply_markup=get_keyboard_main())

    elif data_text == "view_list":
        if not data:
            await query.edit_message_text("🪹 Список пуст.", reply_markup=get_keyboard_main())
        else:
            await query.edit_message_text("📂 Категории:", reply_markup=get_keyboard_categories())

    elif data_text == "add_category":
        context.user_data["state"] = "awaiting_category_name"
        await query.edit_message_text("🆕 Введите название новой категории (можно с эмодзи):")

    elif data_text.startswith("open_"):
        cat = data_text.split("_", 1)[1]
        await query.edit_message_text(f"📦 Категория: {cat}", reply_markup=get_keyboard_items(cat))

    elif data_text.startswith("add_item_"):
        cat = data_text.split("_", 2)[2]
        context.user_data["state"] = f"awaiting_item_{cat}"
        await query.edit_message_text(f"Введите товары для категории «{cat}» (через запятую):")

    elif data_text.startswith("toggle_"):
        _, cat, item = data_text.split("_", 2)
        data[cat]["items"][item] = not data[cat]["items"][item]
        save_data(data)
        await query.edit_message_text(f"📦 {cat}", reply_markup=get_keyboard_items(cat))
        await notify_others(context, user_id, f"🛒 {item} — {'куплено' if data[cat]['items'][item] else 'в списке'} ({cat})")

    elif data_text.startswith("delete_category_"):
        cat = data_text.split("_", 2)[2]
        del data[cat]
        save_data(data)
        await query.edit_message_text("🗂 Категория удалена.", reply_markup=get_keyboard_categories())

    elif data_text == "clear_all":
        data.clear()
        save_data(data)
        await query.edit_message_text("🧹 Всё очищено!", reply_markup=get_keyboard_main())

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Нет доступа.")
        return

    state = context.user_data.get("state")

    if state == "awaiting_category_name":
        text = update.message.text.strip()
        data[text] = {"emoji": "", "items": {}}
        save_data(data)
        context.user_data["state"] = None
        await update.message.reply_text(f"✅ Категория «{text}» добавлена.", reply_markup=get_keyboard_categories())
        await notify_others(context, user_id, f"🆕 Добавлена категория «{text}»")

    elif state and state.startswith("awaiting_item_"):
        cat = state.split("_", 2)[2]
        items = [i.strip() for i in update.message.text.split(",") if i.strip()]
        for item in items:
            data[cat]["items"][item] = False
        save_data(data)
        context.user_data["state"] = None
        await update.message.reply_text(f"✅ Добавлено {len(items)} товаров в «{cat}».", reply_markup=get_keyboard_items(cat))
        await notify_others(context, user_id, f"📦 В категорию «{cat}» добавлены: {', '.join(items)}")

    else:
        await update.message.reply_text("⚙️ Используйте кнопки меню.", reply_markup=get_keyboard_main())

async def notify_others(context, user_id, message):
    for uid in ALLOWED_USERS:
        if uid != user_id:
            try:
                await context.bot.send_message(uid, message)
            except:
                pass

# ====== Основной запуск ======
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
