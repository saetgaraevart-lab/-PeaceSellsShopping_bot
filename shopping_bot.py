import os
import json
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "ВАШ_ТОКЕН_ТУТ"  # вставляем токены прямо
USERS = [431417737, 1117100895]

DATA_FILE = "shopping_data.json"

# Загружаем или создаем файл
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"categories": {}}, f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

app = Flask(__name__)
bot = Bot(BOT_TOKEN)

# --- HELPERS ---

def get_categories_keyboard():
    data = load_data()
    keyboard = []
    for cat, info in data["categories"].items():
        keyboard.append([InlineKeyboardButton(f"{info.get('emoji','')} {cat}", callback_data=f"cat:{cat}")])
    keyboard.append([InlineKeyboardButton("➕ Добавить категорию", callback_data="add_cat")])
    return InlineKeyboardMarkup(keyboard)

def get_items_keyboard(category):
    data = load_data()
    items = data["categories"].get(category, {}).get("items", [])
    keyboard = []
    for item in items:
        status = "✅" if item.get("bought", False) else "❌"
        keyboard.append([
            InlineKeyboardButton(f"{status} {item['name']}", callback_data=f"item:{category}:{item['name']}"),
            InlineKeyboardButton("❌", callback_data=f"del:{category}:{item['name']}")
        ])
    keyboard.append([InlineKeyboardButton("➕ Добавить товар", callback_data=f"add_item:{category}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])
    return InlineKeyboardMarkup(keyboard)

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню:", reply_markup=get_categories_keyboard())

# --- CALLBACK HANDLER ---

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()

    if query.data == "menu":
        await query.edit_message_text("Главное меню:", reply_markup=get_categories_keyboard())
        return

    if query.data.startswith("cat:"):
        category = query.data.split(":", 1)[1]
        await query.edit_message_text(f"Категория: {category}", reply_markup=get_items_keyboard(category))
        return

    if query.data.startswith("item:"):
        _, category, item_name = query.data.split(":", 2)
        items = data["categories"][category]["items"]
        for item in items:
            if item["name"] == item_name:
                item["bought"] = not item.get("bought", False)
                break
        save_data(data)
        await query.edit_message_text(f"Категория: {category}", reply_markup=get_items_keyboard(category))
        return

    if query.data.startswith("del:"):
        _, category, item_name = query.data.split(":", 2)
        items = data["categories"][category]["items"]
        data["categories"][category]["items"] = [i for i in items if i["name"] != item_name]
        save_data(data)
        await query.edit_message_text(f"Категория: {category}", reply_markup=get_items_keyboard(category))
        return

    if query.data.startswith("add_cat"):
        await query.edit_message_text("Напишите название новой категории в чат:")
        context.user_data["action"] = "add_cat"
        return

    if query.data.startswith("add_item:"):
        _, category = query.data.split(":", 1)
        await query.edit_message_text(f"Напишите название товара для категории {category}:")
        context.user_data["action"] = "add_item"
        context.user_data["category"] = category
        return

# --- MESSAGE HANDLER ---

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if context.user_data.get("action") == "add_cat":
        name_parts = text.strip().split(" ")
        name = " ".join(name_parts)
        data = load_data()
        data["categories"][name] = {"emoji": "🛒", "items": []}
        save_data(data)
        context.user_data["action"] = None
        await update.message.reply_text("Категория добавлена!", reply_markup=get_categories_keyboard())
    elif context.user_data.get("action") == "add_item":
        category = context.user_data.get("category")
        data = load_data()
        if category not in data["categories"]:
            await update.message.reply_text("Ошибка: категория не найдена")
            return
        data["categories"][category]["items"].append({"name": text, "bought": False})
        save_data(data)
        context.user_data["action"] = None
        await update.message.reply_text("Товар добавлен!", reply_markup=get_items_keyboard(category))

# --- FLASK ROUTE ---

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "OK"

# --- RUN BOT ---

application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callback_handler))
application.add_handler(CommandHandler("help", start))
application.add_handler(MessageHandler(filters=None, callback=message_handler))

if __name__ == "__main__":
    # Устанавливаем вебхук
    port = int(os.environ.get("PORT", 8443))
    url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"

    async def set_webhook():
        await application.bot.set_webhook(url)
        print(f"Webhook установлен: {url}")

    import asyncio
    asyncio.run(set_webhook())

    # Запуск Flask сервера
    app.run(host="0.0.0.0", port=port)