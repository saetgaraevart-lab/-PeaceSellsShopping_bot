import os
import json
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL")
USERS = [431417737, 1117100895]

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

DATA_FILE = "shopping.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"categories": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

CATEGORY_EMOJI = {
    "овощи": "🥕",
    "фрукты": "🍎",
    "мясо": "🥩",
    "молочное": "🥛",
    "выпечка": "🍞",
    "напитки": "🧃",
}

dispatcher = Dispatcher(bot, None, use_context=True)


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Категории", callback_data="open_categories")],
        [InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category")]
    ])


def start(update, context):
    update.message.reply_text("Выберите действие:", reply_markup=main_menu())


def callback(update, context):
    query = update.callback_query
    command = query.data

    if command == "open_categories":
        return show_categories(query, context)

    if command == "add_category":
        context.user_data["mode"] = "await_category"
        return query.edit_message_text("Введите название категории:")

    if command.startswith("cat_"):
        cat = command[4:]
        return show_items(query, cat)

    if command.startswith("additem_"):
        cat = command[8:]
        context.user_data["mode"] = f"additem:{cat}"
        return query.edit_message_text(f"Введите товар для {cat}:")

    if command.startswith("toggle_"):
        cat, item = command[7:].split(":")
        data["categories"][cat]["items"][item] = not data["categories"][cat]["items"][item]
        save_data(data)
        return show_items(query, cat)

    if command.startswith("del_"):
        cat, item = command[4:].split(":")
        data["categories"][cat]["items"].pop(item, None)
        save_data(data)
        return show_items(query, cat)


def show_categories(query, context):
    if not data["categories"]:
        return query.edit_message_text("Категорий нет.", reply_markup=main_menu())

    keyboard = []
    for cat in data["categories"]:
        emoji = CATEGORY_EMOJI.get(cat.lower(), "📁")
        keyboard.append([InlineKeyboardButton(f"{emoji} {cat}", callback_data=f"cat_{cat}")])

    keyboard.append([InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category")])

    query.edit_message_text("Категории:", reply_markup=InlineKeyboardMarkup(keyboard))


def show_items(query, cat):
    items = data["categories"][cat]["items"]
    keyboard = []

    for name, bought in items.items():
        mark = "✅" if bought else "⬜"
        keyboard.append([
            InlineKeyboardButton(f"{mark} {name}", callback_data=f"toggle_{cat}:{name}"),
            InlineKeyboardButton("❌", callback_data=f"del_{cat}:{name}")
        ])

    keyboard.append([InlineKeyboardButton("➕ Добавить", callback_data=f"additem_{cat}")])
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="open_categories")])

    query.edit_message_text(f"Категория: {cat}", reply_markup=InlineKeyboardMarkup(keyboard))


def text(update, context):
    mode = context.user_data.get("mode")

    if mode == "await_category":
        cat = update.message.text.strip()
        data["categories"][cat] = {"items": {}}
        save_data(data)
        context.user_data["mode"] = None
        return update.message.reply_text("Категория создана.", reply_markup=main_menu())

    if mode and mode.startswith("additem:"):
        cat = mode.split(":")[1]
        item = update.message.text.strip()
        data["categories"][cat]["items"][item] = False
        save_data(data)
        context.user_data["mode"] = None
        return update.message.reply_text("Добавлено!", reply_markup=main_menu())

    update.message.reply_text("Используйте меню.", reply_markup=main_menu())


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200


@app.route("/")
def home():
    return "OK"


if __name__ == "__main__":
    bot.delete_webhook()
    bot.set_webhook(url=f"{PUBLIC_URL}/{BOT_TOKEN}")

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(callback))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, text))

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)