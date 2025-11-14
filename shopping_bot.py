import os
import json
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = "ВАШ_ТОКЕН_ЗДЕСЬ"
USER_IDS = [431417737, 1117100895]  # Ваши ID пользователей

DATA_FILE = "data.json"

app = Flask(__name__)

# Загрузка данных
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {"categories": {}}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main_menu_keyboard():
    buttons = [InlineKeyboardButton(cat + " " + data["categories"][cat]["emoji"],
                                    callback_data=f"category:{cat}")
               for cat in data["categories"]]
    buttons.append(InlineKeyboardButton("Добавить категорию ➕", callback_data="add_category"))
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_split = query.data.split(":")
    
    if data_split[0] == "category":
        cat = data_split[1]
        items = data["categories"][cat]["items"]
        text = f"Категория {cat} {data['categories'][cat]['emoji']}:\n"
        for i, item in enumerate(items):
            status = "✅" if item.get("bought") else "❌"
            text += f"{i+1}. {item['name']} {status}\n"
        await query.edit_message_text(text, reply_markup=category_keyboard(cat))
    
    elif data_split[0] == "add_category":
        await query.edit_message_text("Отправьте название новой категории и эмодзи через пробел, например:\nПродукты 🍎")
        context.user_data["adding_category"] = True
    
    elif data_split[0] == "add_item":
        cat = data_split[1]
        await query.edit_message_text(f"Отправьте название товара для категории {cat}:")
        context.user_data["adding_item"] = cat
    
    elif data_split[0] == "delete_item":
        cat, idx = data_split[1], int(data_split[2])
        removed_item = data["categories"][cat]["items"].pop(idx)
        save_data()
        await query.edit_message_text(f"Товар {removed_item['name']} удалён", reply_markup=category_keyboard(cat))
    
    elif data_split[0] == "toggle_bought":
        cat, idx = data_split[1], int(data_split[2])
        item = data["categories"][cat]["items"][idx]
        item["bought"] = not item.get("bought", False)
        save_data()
        status_text = "✅ Куплено" if item["bought"] else "❌ Не куплено"
        await query.edit_message_text(f"{item['name']} - {status_text}", reply_markup=category_keyboard(cat))

        # Уведомление другим пользователям
        for uid in USER_IDS:
            if uid != update.effective_user.id:
                try:
                    await context.bot.send_message(chat_id=uid,
                        text=f"{update.effective_user.first_name} пометил товар '{item['name']}' как {status_text} в категории {cat}")
                except Exception as e:
                    print(f"Не удалось отправить уведомление пользователю {uid}: {e}")

def category_keyboard(cat):
    items = data["categories"][cat]["items"]
    buttons = []
    for i, item in enumerate(items):
        buttons.append([
            InlineKeyboardButton(f"✅ {item['name']}" if item.get("bought") else f"❌ {item['name']}",
                                 callback_data=f"toggle_bought:{cat}:{i}"),
            InlineKeyboardButton("Удалить", callback_data=f"delete_item:{cat}:{i}")
        ])
    buttons.append([InlineKeyboardButton("Добавить товар ➕", callback_data=f"add_item:{cat}")])
    buttons.append([InlineKeyboardButton("Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("adding_category"):
        text = update.message.text.strip()
        if " " in text:
            name, emoji = text.rsplit(" ", 1)
        else:
            name, emoji = text, "🗂️"
        data["categories"][name] = {"emoji": emoji, "items": []}
        save_data()
        await update.message.reply_text(f"Категория {name} {emoji} добавлена", reply_markup=main_menu_keyboard())
        context.user_data["adding_category"] = False
    
    elif context.user_data.get("adding_item"):
        cat = context.user_data["adding_item"]
        item_name = update.message.text.strip()
        data["categories"][cat]["items"].append({"name": item_name, "bought": False})
        save_data()
        await update.message.reply_text(f"Товар {item_name} добавлен в категорию {cat}", reply_markup=category_keyboard(cat))
        context.user_data["adding_item"] = None

    elif update.message.text.lower() == "/start":
        await start(update, context)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.create_task(application.update_queue.put(update))
    return "OK"

@app.route("/")
def index():
    return "Бот работает!"

application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callback_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    application.bot = application.bot
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8443)))