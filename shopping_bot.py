import os
import json
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

DATA_FILE = "shopping.json"

USERS = [431417737, 1117100895]

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


def build_main_menu():
    keyboard = [
        [InlineKeyboardButton("📂 Категории", callback_data="open_categories")],
        [InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберите действие:", reply_markup=build_main_menu())


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    command = query.data

    if command == "open_categories":
        return await show_categories(query)

    if command == "add_category":
        context.user_data["mode"] = "awaiting_category_name"
        return await query.edit_message_text("Введите название новой категории:")

    if command.startswith("cat_"):
        cat = command[4:]
        return await show_category_items(query, cat)

    if command.startswith("additem_"):
        cat = command[8:]
        context.user_data["mode"] = f"add_item:{cat}"
        return await query.edit_message_text(f"Введите товар для категории «{cat}»:")

    if command.startswith("del_"):
        cat, item = command[4:].split(":", 1)
        data["categories"][cat]["items"].pop(item, None)
        save_data(data)
        
        for uid in USERS:
            if uid != query.from_user.id:
                await context.bot.send_message(uid, f"❌ {item} удалён из категории {cat}")

        return await show_category_items(query, cat)

    if command.startswith("toggle_"):
        cat, item = command[7:].split(":", 1)
        data["categories"][cat]["items"][item] = not data["categories"][cat]["items"][item]
        save_data(data)

        for uid in USERS:
            if uid != query.from_user.id:
                state = "✓" if data["categories"][cat]["items"][item] else "✗"
                await context.bot.send_message(uid, f"🔄 {item} в категории {cat}: {state}")

        return await show_category_items(query, cat)


async def show_categories(query):
    if not data["categories"]:
        return await query.edit_message_text("Категорий нет. Добавьте новую.", reply_markup=build_main_menu())

    keyboard = []
    for cat in data["categories"]:
        emoji = CATEGORY_EMOJI.get(cat.lower(), "📁")
        keyboard.append([InlineKeyboardButton(f"{emoji} {cat}", callback_data=f"cat_{cat}")])

    keyboard.append([InlineKeyboardButton("➕ Добавить", callback_data="add_category")])

    await query.edit_message_text("Категории:", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_category_items(query, cat):
    items = data["categories"].get(cat, {}).get("items", {})

    keyboard = []

    for item, bought in items.items():
        mark = "✅" if bought else "⬜"
        keyboard.append([
            InlineKeyboardButton(f"{mark} {item}", callback_data=f"toggle_{cat}:{item}"),
            InlineKeyboardButton("❌", callback_data=f"del_{cat}:{item}")
        ])

    keyboard.append([InlineKeyboardButton("➕ Добавить товар", callback_data=f"additem_{cat}")])
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="open_categories")])

    await query.edit_message_text(f"Категория: {cat}", reply_markup=InlineKeyboardMarkup(keyboard))


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")

    if mode == "awaiting_category_name":
        cat = update.message.text.strip()
        data["categories"][cat] = {"items": {}}
        save_data(data)

        for uid in USERS:
            if uid != update.message.from_user.id:
                await context.bot.send_message(uid, f"📂 Добавлена категория: {cat}")

        context.user_data["mode"] = None
        return await update.message.reply_text("Категория создана.", reply_markup=build_main_menu())

    if mode and mode.startswith("add_item:"):
        cat = mode.split(":")[1]
        item = update.message.text.strip()
        data["categories"][cat]["items"][item] = False
        save_data(data)

        for uid in USERS:
            if uid != update.message.from_user.id:
                await context.bot.send_message(uid, f"➕ Добавлен товар: {item} → {cat}")

        context.user_data["mode"] = None
        return await update.message.reply_text("Добавлено.", reply_markup=build_main_menu())

    await update.message.reply_text("Не понимаю. Используйте меню.", reply_markup=build_main_menu())


async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    PUBLIC_URL = os.getenv("PUBLIC_URL")

    if not PUBLIC_URL:
        raise RuntimeError("PUBLIC_URL не найден! Добавь его в Render → Environment.")

    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        webhook_url=f"{PUBLIC_URL}/{BOT_TOKEN}"
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())