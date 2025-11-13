import os
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- Настройки ----------------
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
port = int(os.environ.get("PORT", "5000"))
DATA_FILE = "shopping_data.json"
AUTHORIZED_USERS = [431417737, 1117100895]  # Замените на ваши Telegram ID

# ---------------- Загрузка / сохранение данных ----------------
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        shopping_list = json.load(f)
else:
    shopping_list = {}  # {category: {"emoji": "🥦", "items": [{"name":"Молоко","bought":False}, ...]}}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(shopping_list, f, ensure_ascii=False, indent=2)

# ---------------- Меню ----------------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🛍 Показать список", callback_data="show_list")],
        [InlineKeyboardButton("➕ Добавить товары", callback_data="add_items")],
        [InlineKeyboardButton("📂 Категории", callback_data="categories")],
        [InlineKeyboardButton("🧹 Очистить всё", callback_data="clear_all")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_list_markup():
    keyboard = []
    for cat, info in shopping_list.items():
        emoji = info.get("emoji", "")
        items = info["items"]
        keyboard.append([InlineKeyboardButton(f"{emoji} {cat}", callback_data="none")])
        for item in items:
            name = item["name"]
            status = "✅" if item["bought"] else "❌"
            keyboard.append([
                InlineKeyboardButton(f"{status} {name}", callback_data=f"toggle:{cat}:{name}"),
                InlineKeyboardButton("🗑", callback_data=f"del:{cat}:{name}")
            ])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def categories_markup():
    keyboard = []
    for cat, info in shopping_list.items():
        emoji = info.get("emoji", "")
        keyboard.append([InlineKeyboardButton(f"{emoji} {cat}", callback_data=f"cat:{cat}")])
    keyboard.append([InlineKeyboardButton("➕ Новая категория", callback_data="new_category")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

# ---------------- Обработчики ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in AUTHORIZED_USERS:
        await update.message.reply_text("🚫 У вас нет доступа к боту.")
        return
    await update.message.reply_text(
        "👋 Привет! Я твой бот для покупок.\nВыбери действие:",
        reply_markup=main_menu()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if user_id not in AUTHORIZED_USERS:
        await query.edit_message_text("🚫 У вас нет доступа к боту.")
        return

    # ---------- Главное меню ----------
    if data == "show_list":
        if not shopping_list:
            await query.edit_message_text("🛒 Список пуст.", reply_markup=main_menu())
        else:
            await query.edit_message_text("🛒 Твой список:", reply_markup=build_list_markup())
    elif data == "add_items":
        context.user_data["awaiting_items"] = True
        await query.edit_message_text("Введите товары через запятую. Потом выберите категорию.")
    elif data.startswith("toggle:"):
        _, cat, name = data.split(":", 2)
        for item in shopping_list[cat]["items"]:
            if item["name"] == name:
                item["bought"] = not item["bought"]
        save_data()
        await query.edit_message_text("Обновлено!", reply_markup=build_list_markup())
    elif data.startswith("del:"):
        _, cat, name = data.split(":", 2)
        shopping_list[cat]["items"] = [i for i in shopping_list[cat]["items"] if i["name"] != name]
        save_data()
        await query.edit_message_text("Удалено!", reply_markup=build_list_markup())
    elif data == "clear_all":
        shopping_list.clear()
        save_data()
        await query.edit_message_text("Список очищен!", reply_markup=main_menu())
    elif data == "categories":
        await query.edit_message_text("Выберите категорию:", reply_markup=categories_markup())
    elif data == "new_category":
        context.user_data["awaiting_category_name"] = True
        await query.edit_message_text("Введите название новой категории:")
    elif data.startswith("cat:"):
        category = data.split(":",1)[1]
        context.user_data["selected_category"] = category
        await query.edit_message_text(f"Введите товары для категории {shopping_list[category]['emoji']} {category}:")
        context.user_data["awaiting_items"] = True
    elif data == "back_main":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu())

# ---------- Обработка текста ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    text = update.message.text.strip()
    if update.effective_user.id not in AUTHORIZED_USERS:
        await update.message.reply_text("🚫 У вас нет доступа к боту.")
        return

    # ---------- Новая категория ----------
    if user_data.get("awaiting_category_name"):
        user_data["new_category_name"] = text
        user_data.pop("awaiting_category_name")
        user_data["awaiting_category_emoji"] = True
        await update.message.reply_text("Введите эмодзи для этой категории:")
        return
    if user_data.get("awaiting_category_emoji"):
        emoji = text
        category_name = user_data.pop("new_category_name")
        shopping_list[category_name] = {"emoji": emoji, "items": []}
        save_data()
        user_data.pop("awaiting_category_emoji")
        await update.message.reply_text(f"Категория {emoji} {category_name} добавлена!", reply_markup=main_menu())
        return

    # ---------- Добавление товаров ----------
    if user_data.get("awaiting_items"):
        items = [i.strip() for i in text.split(",") if i.strip()]
        category = user_data.get("selected_category")
        if not category:
            await update.message.reply_text("Выберите категорию через меню '📂 Категории'")
            return
        for item in items:
            shopping_list[category]["items"].append({"name": item, "bought": False})
        save_data()
        user_data.pop("awaiting_items")
        user_data.pop("selected_category", None)
        # Оповещение для других пользователей
        for uid in AUTHORIZED_USERS:
            if uid != update.effective_user.id:
                try:
                    await context.bot.send_message(uid, f"📝 {update.effective_user.first_name} добавил(а): {', '.join(items)} в категорию {shopping_list[category]['emoji']} {category}")
                except:
                    pass
        await update.message.reply_text("Товары добавлены!", reply_markup=main_menu())
        return

# ---------------- Запуск ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    print("Бот запущен...")
    app.run_webhook(
    listen="0.0.0.0",
    port=port,
    url_path=TOKEN,
    webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
)

if __name__ == "__main__":
    main()