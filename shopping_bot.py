#!/usr/bin/env python3
# coding: utf-8

import os
import json
import logging
from urllib.parse import quote, unquote

from flask import Flask, request, abort
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# ---------------- Configuration ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL")  # e.g. https://peacesellsshopping-bot.onrender.com
PORT = int(os.getenv("PORT", "10000"))

# IDs of allowed users (you and your wife)
ALLOWED_USERS = [431417737, 1117100895]

DATA_FILE = "shopping_data.json"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set in environment variables")
if not PUBLIC_URL:
    raise RuntimeError("PUBLIC_URL not set in environment variables (Render public URL)")

# ---------------- Logging ----------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- Flask + Bot ----------------
app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# ---------------- Data helpers ----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        # data structure:
        # {"categories": { "Category Name": {"emoji": "🥦", "items": [ {"name":"Milk","done":False}, ... ] } } }
        return {"categories": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

data = load_data()

# ---------------- Utilities ----------------
def is_allowed_user(user_id):
    return user_id in ALLOWED_USERS

def main_menu_markup():
    kb = [
        [InlineKeyboardButton("📂 Категории", callback_data="show_categories")],
        [InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category")],
        [InlineKeyboardButton("🧹 Очистить всё", callback_data="clear_all")],
    ]
    return InlineKeyboardMarkup(kb)

def categories_markup():
    kb = []
    for cat, info in data["categories"].items():
        emoji = info.get("emoji", "")
        token = quote(cat, safe='')
        kb.append([InlineKeyboardButton(f"{emoji} {cat}", callback_data=f"open_cat|{token}")])
    kb.append([InlineKeyboardButton("⬅ Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(kb)

def category_items_markup(cat):
    items = data["categories"][cat]["items"]
    kb = []
    for idx, it in enumerate(items):
        mark = "✅" if it.get("done") else "🛒"
        # include index to avoid ambiguity when names equal
        kb.append([
            InlineKeyboardButton(f"{mark} {it['name']}", callback_data=f"toggle|{quote(cat, safe='')}|{idx}"),
            InlineKeyboardButton("🗑", callback_data=f"delete|{quote(cat, safe='')}|{idx}")
        ])
    kb.append([InlineKeyboardButton("➕ Добавить товары (через запятую)", callback_data=f"additems|{quote(cat, safe='')}")])
    kb.append([InlineKeyboardButton("⬅ К списку категорий", callback_data="show_categories")])
    return InlineKeyboardMarkup(kb)

# ---------------- Handlers ----------------
def send_notify_except(sender_id, text):
    for uid in ALLOWED_USERS:
        if uid != sender_id:
            try:
                bot.send_message(chat_id=uid, text=text)
            except Exception as e:
                logger.warning("Notify failed to %s: %s", uid, e)

def start(update, context):
    user = update.effective_user
    if not user or not is_allowed_user(user.id):
        update.message.reply_text("⛔ У вас нет доступа к боту.")
        return
    update.message.reply_text("👋 Привет! Главного меню:", reply_markup=main_menu_markup())

def callback_query(update, context):
    query = update.callback_query
    user = query.from_user
    if not user or not is_allowed_user(user.id):
        query.answer()
        query.edit_message_text("⛔ У вас нет доступа.")
        return
    data_tok = query.data
    logger.info("Callback from %s: %s", user.id, data_tok)
    query.answer()

    if data_tok == "main_menu":
        query.edit_message_text("Главное меню:", reply_markup=main_menu_markup())
        return

    if data_tok == "show_categories":
        if not data["categories"]:
            query.edit_message_text("📭 Пока нет категорий. Добавьте первую.", reply_markup=main_menu_markup())
            return
        query.edit_message_text("📂 Категории:", reply_markup=categories_markup())
        return

    if data_tok == "add_category":
        context.user_data['mode'] = 'awaiting_category'
        query.edit_message_text("Введите новую категорию. Формат: `эмодзи` `Название категории` или просто `Название`.")
        return

    if data_tok.startswith("open_cat|"):
        _, token = data_tok.split("|", 1)
        cat = unquote(token)
        if cat not in data["categories"]:
            query.edit_message_text("⚠ Категория не найдена.", reply_markup=categories_markup())
            return
        info = data["categories"][cat]
        query.edit_message_text(f"📦 {info.get('emoji','')} *{cat}*", parse_mode='Markdown', reply_markup=category_items_markup(cat))
        return

    if data_tok.startswith("additems|"):
        _, token = data_tok.split("|", 1)
        cat = unquote(token)
        context.user_data['mode'] = 'awaiting_items'
        context.user_data['cat_for_items'] = cat
        query.edit_message_text(f"Введите товары через запятую для категории *{cat}*:", parse_mode='Markdown')
        return

    if data_tok.startswith("toggle|"):
        _, cat_token, idx_str = data_tok.split("|", 2)
        cat = unquote(cat_token)
        idx = int(idx_str)
        try:
            item = data["categories"][cat]["items"][idx]
        except Exception:
            query.edit_message_text("⚠ Элемент не найден.", reply_markup=category_items_markup(cat))
            return
        item['done'] = not bool(item.get('done'))
        save_data(data)
        send_notify_except(user.id, f"🔁 Статус: {'куплено' if item['done'] else 'в списке'} — {item['name']} ({cat})")
        query.edit_message_text(f"📦 {cat}", reply_markup=category_items_markup(cat))
        return

    if data_tok.startswith("delete|"):
        _, cat_token, idx_str = data_tok.split("|", 2)
        cat = unquote(cat_token)
        idx = int(idx_str)
        try:
            item = data["categories"][cat]["items"].pop(idx)
            save_data(data)
            send_notify_except(user.id, f"🗑 Удалено: {item['name']} ({cat})")
            query.edit_message_text(f"🗑 Удалено: {item['name']}", reply_markup=category_items_markup(cat))
        except Exception:
            query.edit_message_text("⚠ Ошибка удаления.", reply_markup=category_items_markup(cat))
        return

    if data_tok == "clear_all":
        data["categories"].clear()
        save_data(data)
        send_notify_except(user.id, "🧹 Список полностью очищён")
        query.edit_message_text("🧹 Всё очищено!", reply_markup=main_menu_markup())
        return

    query.edit_message_text("⚠ Неизвестное действие.", reply_markup=main_menu_markup())

def text_message(update, context):
    user = update.effective_user
    if not user or not is_allowed_user(user.id):
        update.message.reply_text("⛔ У вас нет доступа.")
        return

    txt = (update.message.text or "").strip()
    mode = context.user_data.get('mode')
    logger.info("Text from %s mode=%s: %s", user.id, mode, txt[:100])

    if mode == 'awaiting_category':
        # Accept "emoji name" or "name"
        context.user_data['mode'] = None
        parts = txt.split(" ", 1)
        if len(parts) == 1:
            emoji = ""
            name = parts[0].strip()
        else:
            emoji_candidate, rest = parts[0].strip(), parts[1].strip()
            emoji = emoji_candidate
            name = rest
        if not name:
            update.message.reply_text("⚠ Неверный формат. Попробуйте ещё раз.", reply_markup=main_menu_markup())
            return
        if name in data["categories"]:
            update.message.reply_text("⚠ Такая категория уже существует.", reply_markup=categories_markup())
            return
        data["categories"][name] = {"emoji": emoji, "items": []}
        save_data(data)
        send_notify_except(user.id, f"➕ Добавлена категория: {emoji} {name}")
        update.message.reply_text(f"✅ Категория добавлена: {emoji} {name}", reply_markup=categories_markup())
        return

    if mode == 'awaiting_items':
        cat = context.user_data.get('cat_for_items')
        context.user_data['mode'] = None
        context.user_data.pop('cat_for_items', None)
        if not cat or cat not in data["categories"]:
            update.message.reply_text("⚠ Категория не найдена. Попробуйте через меню.", reply_markup=main_menu_markup())
            return
        items = [i.strip() for i in txt.split(",") if i.strip()]
        if not items:
            update.message.reply_text("⚠ Нечего добавлять.")
            return
        for it in items:
            data["categories"][cat]["items"].append({"name": it, "done": False})
        save_data(data)
        send_notify_except(user.id, f"➕ В {cat} добавлены: {', '.join(items)}")
        update.message.reply_text(f"✅ Добавлено {len(items)} товаров в категорию {cat}", reply_markup=category_items_markup(cat))
        return

    # Fallback
    update.message.reply_text("Используйте меню /start или кнопки.", reply_markup=main_menu_markup())

# ---------------- Flask webhook endpoint ----------------
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    if request.method == "POST":
        try:
            update = Update.de_json(request.get_json(force=True), bot)
            dispatcher.process_update(update)
        except Exception as e:
            logger.exception("Failed to process update: %s", e)
            return "OK", 200
        return "OK", 200
    else:
        abort(403)

@app.route("/", methods=['GET'])
def index():
    return "Bot is running", 200

# ---------------- Register handlers ----------------
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(callback_query))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), text_message))

# ---------------- Main: set webhook + run Flask ----------------
if __name__ == "__main__":
    # set webhook
    webhook_url = f"{PUBLIC_URL}/{BOT_TOKEN}"
    logger.info("Setting webhook to %s", webhook_url)
    try:
        bot.delete_webhook()
        bot.set_webhook(url=webhook_url)
    except Exception as e:
        logger.exception("Failed to set webhook: %s", e)
        raise

    logger.info("Starting Flask app on port %s", PORT)
    app.run(host="0.0.0.0", port=PORT)