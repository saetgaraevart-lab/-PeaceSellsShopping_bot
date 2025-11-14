import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# -----------------------
# Настройки
# -----------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "shopping_list.json"
USERS = [431417737, 1117100895]  # Юзеры, которым бот доступен

# -----------------------
# Загрузка / Сохранение данных
# -----------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"categories": {}}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# -----------------------
# Команды
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Категории", callback_data="show_categories")],
        [InlineKeyboardButton("Добавить категорию", callback_data="add_category")],
    ]
    await update.message.reply_text(
        "Привет! Выберите действие:", reply_markup=InlineKeyboardMarkup(keyboard)
    )

# -----------------------
# Основные хендлеры
# -----------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    if user_id not in USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return

    await update.message.reply_text("Используйте кнопки меню.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in USERS:
        await query.edit_message_text("У вас нет доступа к этому боту.")
        return

    data_loaded = load_data()
    categories = data_loaded["categories"]

    # Главное меню
    if query.data == "show_categories":
        if not categories:
            await query.edit_message_text("Категории пусты.")
            return
        keyboard = [
            [InlineKeyboardButton(f"{emoji} {name}", callback_data=f"cat:{name}")]
            for name, emoji in categories.items()
        ]
        keyboard.append([InlineKeyboardButton("⬅ Главное меню", callback_data="main")])
        await query.edit_message_text("Категории:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif query.data == "add_category":
        await query.edit_message_text("Отправьте название категории с эмодзи через пробел, например:\n🍎 Фрукты")
        context.user_data["awaiting_category"] = True
        return

    elif query.data.startswith("cat:"):
        cat_name = query.data[4:]
        items = categories.get(cat_name, {}).get("items", [])
        if not items:
            text = "Список пуст."
        else:
            text = "\n".join(
                [f"[{'✓' if item.get('bought') else ' '}] {item['name']}" for item in items]
            )
        keyboard = [
            [InlineKeyboardButton("Добавить товар", callback_data=f"add_item:{cat_name}")],
            [InlineKeyboardButton("⬅ Категории", callback_data="show_categories")],
        ]
        await query.edit_message_text(text or "Список пуст.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif query.data.startswith("add_item:"):
        cat_name = query.data[9:]
        await query.edit_message_text(f"Отправьте название товара для категории {cat_name}")
        context.user_data["awaiting_item"] = cat_name
        return

    elif query.data == "main":
        await start(update, context)
        return

# -----------------------
# MessageHandler для ввода категорий и товаров
# -----------------------
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return

    text = update.message.text
    if context.user_data.get("awaiting_category"):
        try:
            emoji, *name_parts = text.split()
            cat_name = " ".join(name_parts)
            data["categories"][cat_name] = {"emoji": emoji, "items": []}
            save_data(data)
            await update.message.reply_text(f"Категория {emoji} {cat_name} добавлена.")
        except Exception:
            await update.message.reply_text("Неправильный формат. Пример: 🍎 Фрукты")
        context.user_data["awaiting_category"] = False
        return

    elif context.user_data.get("awaiting_item"):
        cat_name = context.user_data["awaiting_item"]
        data["categories"][cat_name]["items"].append({"name": text, "bought": False})
        save_data(data)
        await update.message.reply_text(f"Товар '{text}' добавлен в категорию {cat_name}")
        context.user_data["awaiting_item"] = False
        return

    await update.message.reply_text("Используйте кнопки меню.")

# -----------------------
# Main
# -----------------------
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    # Кнопки
    application.add_handler(CallbackQueryHandler(handle_callback))
    # Сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Запуск через вебхук
    port = int(os.environ.get("PORT", 8443))
    webhook_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/{BOT_TOKEN}"
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=webhook_url,
    )

if __name__ == "__main__":
    main()