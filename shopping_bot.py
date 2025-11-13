import os
import json
import logging
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
)

# === Настройки ===
TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://peacesellsshopping-bot.onrender.com")
PORT = int(os.getenv("PORT", "10000"))
DATA_FILE = "data.json"
ALLOWED_USERS = [431417737, 1117100895]

# === Flask ===
app = Flask(__name__)

# === Логирование ===
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Функции для работы с данными ===
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"categories": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# === Проверка доступа ===
def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id in ALLOWED_USERS


# === Хендлеры ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    keyboard = [
        [InlineKeyboardButton("🛍 Список", callback_data="list"),
         InlineKeyboardButton("➕ Добавить", callback_data="add")],
        [InlineKeyboardButton("📦 Категории", callback_data="categories"),
         InlineKeyboardButton("🧹 Очистить", callback_data="clear")]
    ]
    await update.message.reply_text(
        "Привет 👋! Это твой бот для покупок.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Используй: /add <категория> <товар>")
        return
    category, *item = context.args
    item = " ".join(item)
    if category not in data["categories"]:
        data["categories"][category] = {"emoji": "🛒", "items": []}
    data["categories"][category]["items"].append({"name": item, "done": False})
    save_data(data)
    await update.message.reply_text(f"✅ Добавлено в {category}: {item}")


async def list_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    text = ""
    for cat, info in data["categories"].items():
        text += f"\n{info['emoji']} *{cat}*\n"
        for i, it in enumerate(info["items"], 1):
            mark = "✅" if it["done"] else "⬜"
            text += f"{mark} {i}. {it['name']}\n"
    if not text:
        text = "Список пуст 🛒"
    await update.message.reply_text(text, parse_mode="Markdown")


async def toggle_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Используй: /done <категория> <номер>")
        return
    category, index = context.args[0], int(context.args[1]) - 1
    if category in data["categories"] and 0 <= index < len(data["categories"][category]["items"]):
        item = data["categories"][category]["items"][index]
        item["done"] = not item["done"]
        save_data(data)
        await update.message.reply_text(
            f"{'✅ Куплено' if item['done'] else '↩️ Вернул в список'}: {item['name']}"
        )
    else:
        await update.message.reply_text("Не найдено.")


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    data["categories"].clear()
    save_data(data)
    await update.message.reply_text("🧹 Список очищен!")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "list":
        fake_update = Update.de_json(
            {"message": {"text": "/list", "chat": {"id": query.message.chat_id}, "from": {"id": query.from_user.id}}},
            context.bot
        )
        await list_items(fake_update, context)
    elif query.data == "clear":
        fake_update = Update.de_json(
            {"message": {"text": "/clear", "chat": {"id": query.message.chat_id}, "from": {"id": query.from_user.id}}},
            context.bot
        )
        await clear(fake_update, context)
    elif query.data == "add":
        await query.message.reply_text("✍️ Используй команду:\n/add <категория> <товар>")
    elif query.data == "categories":
        cats = "\n".join(f"{v['emoji']} {k}" for k, v in data["categories"].items()) or "Нет категорий"
        await query.message.reply_text(f"📦 Категории:\n{cats}")


# === Flask endpoint ===
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok", 200


@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200


# === Инициализация Telegram ===
from telegram import Bot
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add", add_item))
application.add_handler(CommandHandler("list", list_items))
application.add_handler(CommandHandler("done", toggle_item))
application.add_handler(CommandHandler("clear", clear))
application.add_handler(MessageHandler(filters.COMMAND, start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))
application.add_handler(MessageHandler(filters.ALL, start))
from telegram.ext import CallbackQueryHandler

application.add_handler(CallbackQueryHandler(callback_handler))
# === Webhook установка ===
@app.before_first_request
def init_webhook():
    bot.delete_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    logger.info("✅ Webhook установлен!")

# === Запуск ===
if __name__ == "__main__":
    logger.info(f"🚀 Бот запущен на порту {PORT}")
    app.run(host="0.0.0.0", port=PORT)
