import os
import json
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# --- Настройка ---
DATA_FILE = "shopping_data.json"
ALLOWED_USERS = [431417737, 1117100895]

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("Нет BOT_TOKEN в переменных окружения!")

# --- Загрузка/сохранение JSON ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"categories": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# ----------------------- UI -----------------------
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Категории", callback_data="open_categories")],
        [InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category")],
    ])

def categories_keyboard():
    buttons = []
    for name, info in data["categories"].items():
        emoji = info.get("emoji", "📁")
        buttons.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f"open_cat|{name}")])
    return InlineKeyboardMarkup(buttons + [[InlineKeyboardButton("⬅ Назад", callback_data="back_main")]])

def category_items_keyboard(cat_name):
    items = data["categories"][cat_name]["items"]
    btns = []

    for i, item in enumerate(items):
        status = "✅" if item["done"] else "🛒"
        btns.append([
            InlineKeyboardButton(f"{status} {item['name']}", callback_data=f"toggle_item|{cat_name}|{i}")
        ])

    btns.append([InlineKeyboardButton("➕ Добавить товар", callback_data=f"add_item|{cat_name}")])
    btns.append([InlineKeyboardButton("🗑 Удалить товар", callback_data=f"delete_item|{cat_name}")])
    btns.append([InlineKeyboardButton("⬅ Назад", callback_data="open_categories")])

    return InlineKeyboardMarkup(btns)

def deletion_keyboard(cat_name):
    items = data["categories"][cat_name]["items"]
    btns = []
    for i, item in enumerate(items):
        btns.append([
            InlineKeyboardButton(f"Удалить {item['name']}", callback_data=f"confirm_delete|{cat_name}|{i}")
        ])
    btns.append([InlineKeyboardButton("⬅ Назад", callback_data=f"open_cat|{cat_name}")])
    return InlineKeyboardMarkup(btns)

# ----------------------- Handlers -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа ❌")
        return

    await update.message.reply_text("Привет! Это совместный список покупок 🛍", reply_markup=main_menu())


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await query.edit_message_text("Нет доступа ❌")
        return

    action = query.data

    # --- Главное меню ---
    if action == "open_categories":
        await query.edit_message_text("Категории:", reply_markup=categories_keyboard())

    elif action == "back_main":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu())

    # --- Создание категорий ---
    elif action == "add_category":
        context.user_data["mode"] = "adding_category"
        await query.edit_message_text("Введите название категории и эмодзи через точку:\n\nНапример:\n🍞 Хлеб и выпечка")

    # --- Открыть категорию ---
    elif action.startswith("open_cat"):
        _, cat_name = action.split("|")
        await query.edit_message_text(f"Категория: {cat_name}", reply_markup=category_items_keyboard(cat_name))

    # --- Добавить товар ---
    elif action.startswith("add_item"):
        _, cat_name = action.split("|")
        context.user_data["mode"] = "adding_item"
        context.user_data["cat"] = cat_name
        await query.edit_message_text("Введите название товара:")

    # --- Переключить статус ---
    elif action.startswith("toggle_item"):
        _, cat, idx = action.split("|")
        idx = int(idx)
        data["categories"][cat]["items"][idx]["done"] ^= True
        save_data(data)

        await query.edit_message_text(f"Категория: {cat}", reply_markup=category_items_keyboard(cat))

        # Оповестить второго пользователя
        for uid in ALLOWED_USERS:
            if uid != user_id:
                await context.bot.send_message(uid, f"Изменён статус товара в категории {cat}")

    # --- Удаление ---
    elif action.startswith("delete_item"):
        _, cat = action.split("|")
        await query.edit_message_text("Выберите товар для удаления:", reply_markup=deletion_keyboard(cat))

    elif action.startswith("confirm_delete"):
        _, cat, idx = action.split("|")
        idx = int(idx)
        deleted = data["categories"][cat]["items"].pop(idx)
        save_data(data)

        await query.edit_message_text(
            f"Удалено: {deleted['name']}\nКатегория: {cat}",
            reply_markup=category_items_keyboard(cat)
        )

        # Уведомление
        for uid in ALLOWED_USERS:
            if uid != user_id:
                await context.bot.send_message(uid, f"Товар удалён: {deleted['name']}")

# ----------------------- Text Input -----------------------
async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа ❌")
        return

    mode = context.user_data.get("mode")

    # --- Добавление категории ---
    if mode == "adding_category":
        text = update.message.text.strip()
        parts = text.split(" ", 1)

        if len(parts) == 1:
            emoji = "📁"
            name = parts[0]
        else:
            emoji, name = parts[0], parts[1]

        data["categories"][name] = {"emoji": emoji, "items": []}
        save_data(data)

        context.user_data["mode"] = None
        await update.message.reply_text("Категория добавлена!", reply_markup=categories_keyboard())
        return

    # --- Добавление товара ---
    if mode == "adding_item":
        cat = context.user_data["cat"]
        item_name = update.message.text.strip()

        data["categories"][cat]["items"].append({"name": item_name, "done": False})
        save_data(data)

        context.user_data["mode"] = None
        context.user_data["cat"] = None
        await update.message.reply_text(
            f"Товар добавлен в категорию {cat}!",
            reply_markup=category_items_keyboard(cat)
        )

        # Уведомление второго пользователя
        for uid in ALLOWED_USERS:
            if uid != user_id:
                await context.bot.send_message(uid, f"Добавлен новый товар в категории {cat}: {item_name}")

# ----------------------------------------------------------
async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input))

    PORT = int(os.environ.get("PORT", "10000"))

    # --- Главный запуск webhook ---
    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}",
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
