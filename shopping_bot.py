import os
import json
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ----------------- Настройки -----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # токен в environment variables
JSON_FILE = "shopping_list.json"

# ----------------- Файл JSON -----------------
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({"categories": {}}, f, ensure_ascii=False, indent=2)

def load_data():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ----------------- Flask -----------------
app = Flask(__name__)
bot = Bot(BOT_TOKEN)

# ----------------- Главное меню -----------------
def build_main_menu():
    data = load_data()
    buttons = [
        [InlineKeyboardButton(f"{v['emoji']} {k}", callback_data=f"cat_{k}")]
        for k, v in data["categories"].items()
    ]
    buttons.append([InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category")])
    return InlineKeyboardMarkup(buttons)

# ----------------- Команды -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню:", reply_markup=build_main_menu())

# ----------------- CallbackQuery -----------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()

    # --- Главное меню ---
    if query.data == "main_menu":
        await query.edit_message_text("Главное меню:", reply_markup=build_main_menu())

    # --- Добавление категории ---
    elif query.data == "add_category":
        await query.edit_message_text("Напиши название категории через пробел (можно с эмодзи в начале):")
        context.user_data["adding_category"] = True

    # --- Категории ---
    elif query.data.startswith("cat_"):
        cat_name = query.data[4:]
        cat = data["categories"].get(cat_name, {"items": [], "emoji": "❓"})
        buttons = [
            [InlineKeyboardButton(f"✔️ {i['name']}" if i.get("bought") else f"❌ {i['name']}",
                                  callback_data=f"toggle_{cat_name}_{idx}"),
             InlineKeyboardButton("❌", callback_data=f"delitem_{cat_name}_{idx}")]
            for idx, i in enumerate(cat["items"])
        ]
        buttons.append([InlineKeyboardButton("➕ Добавить товар", callback_data=f"add_item_{cat_name}")])
        buttons.append([InlineKeyboardButton("🖊 Изменить эмодзи", callback_data=f"edit_emoji_{cat_name}")])
        buttons.append([InlineKeyboardButton("❌ Удалить категорию", callback_data=f"delcat_{cat_name}")])
        buttons.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])
        await query.edit_message_text(f"{cat['emoji']} {cat_name}", reply_markup=InlineKeyboardMarkup(buttons))

    # --- Переключение куплено/не куплено ---
    elif query.data.startswith("toggle_"):
        _, cat_name, idx = query.data.split("_")
        idx = int(idx)
        item = data["categories"][cat_name]["items"][idx]
        item["bought"] = not item.get("bought", False)
        save_data(data)
        await callback_handler(update, context)

    # --- Удаление товара ---
    elif query.data.startswith("delitem_"):
        _, cat_name, idx = query.data.split("_")
        idx = int(idx)
        data["categories"][cat_name]["items"].pop(idx)
        save_data(data)
        await callback_handler(update, context)

    # --- Добавление товара ---
    elif query.data.startswith("add_item_"):
        cat_name = query.data[9:]
        await query.edit_message_text("Напиши название товара:")
        context.user_data["adding_item"] = cat_name

    # --- Изменение эмодзи ---
    elif query.data.startswith("edit_emoji_"):
        cat_name = query.data[11:]
        await query.edit_message_text("Напиши новый эмодзи для категории:")
        context.user_data["editing_emoji"] = cat_name

    # --- Удаление категории ---
    elif query.data.startswith("delcat_"):
        cat_name = query.data[7:]
        data["categories"].pop(cat_name, None)
        save_data(data)
        await callback_handler(update, context)

# ----------------- Обработка текста -----------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    data = load_data()

    # --- Добавление категории ---
    if context.user_data.get("adding_category"):
        parts = text.strip().split(" ", 1)
        if len(parts) == 1:
            emoji = "❓"
            name = parts[0]
        else:
            emoji = parts[0]
            name = parts[1]
        data["categories"][name] = {"emoji": emoji, "items": []}
        save_data(data)
        context.user_data.pop("adding_category")
        await update.message.reply_text("Категория добавлена.", reply_markup=build_main_menu())

    # --- Добавление товара ---
    elif "adding_item" in context.user_data:
        cat_name = context.user_data.pop("adding_item")
        data["categories"][cat_name]["items"].append({"name": text, "bought": False})
        save_data(data)
        await update.message.reply_text(f"Товар добавлен в {cat_name}.")
        await update.message.reply_text("Главное меню:", reply_markup=build_main_menu())

    # --- Изменение эмодзи ---
    elif "editing_emoji" in context.user_data:
        cat_name = context.user_data.pop("editing_emoji")
        data["categories"][cat_name]["emoji"] = text.strip()
        save_data(data)
        await update.message.reply_text("Эмодзи обновлено.", reply_markup=build_main_menu())

# ----------------- Flask webhook -----------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application = app.config["application"]
    application.update_queue.put(update)
    return "OK"

# ----------------- Основной запуск -----------------
if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    app.config["application"] = application

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters=None, callback=text_handler))

    port = int(os.environ.get("PORT", 5000))
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    )