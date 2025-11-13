import json
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

import os
TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = Path("shopping_list.json")

# Загрузка / сохранение данных
if DATA_FILE.exists():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        shopping_data = json.load(f)
else:
    shopping_data = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(shopping_data, f, ensure_ascii=False, indent=2)

# --- Команды ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 🛍️ Я бот для списка покупок.\n\n"
        "Команды:\n"
        "/add [категория] [позиции через запятую]\n"
        "Например: /add продукты молоко, хлеб, сыр\n\n"
        "/list — показать список\n"
        "/clear — очистить всё"
    )

async def add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❗ Пример: /add продукты молоко, хлеб, сыр")
        return

    category = context.args[0].lower()
    items_text = " ".join(context.args[1:])
    items = [i.strip() for i in items_text.split(",") if i.strip()]

    if category not in shopping_data:
        shopping_data[category] = []

    shopping_data[category].extend(items)
    save_data()

    added_items = "\n".join(f"• {item}" for item in items)
    await update.message.reply_text(
        f"✅ Добавлено в категорию *{category}*:\n{added_items}",
        parse_mode="Markdown"
    )

async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not shopping_data:
        await update.message.reply_text("🛒 Список пуст.")
        return

    text = "🛍️ *Твой список покупок:*\n\n"
    for category, items in shopping_data.items():
        text += f"📂 *{category.capitalize()}*\n"
        for i, item in enumerate(items, start=1):
            text += f"{i}. {item}\n"
        text += "\n"

    # Кнопки
    keyboard = [
        [InlineKeyboardButton("🗑 Очистить всё", callback_data="clear_all")]
    ]
    for cat in shopping_data.keys():
        keyboard.append([InlineKeyboardButton(f"🧹 Очистить {cat}", callback_data=f"clear_cat:{cat}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def clear_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shopping_data.clear()
    save_data()
    await update.message.reply_text("🧹 Список полностью очищен!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "clear_all":
        shopping_data.clear()
        save_data()
        await query.edit_message_text("🧹 Список полностью очищен!")
    elif data.startswith("clear_cat:"):
        cat = data.split(":", 1)[1]
        if cat in shopping_data:
            del shopping_data[cat]
            save_data()
            await query.edit_message_text(f"🧹 Категория *{cat}* очищена!", parse_mode="Markdown")

# --- Запуск приложения ---
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add_item))
app.add_handler(CommandHandler("list", show_list))
app.add_handler(CommandHandler("clear", clear_list))
app.add_handler(CallbackQueryHandler(button_callback))

print("✅ Бот запущен. Нажми Ctrl+C, чтобы остановить.")
app.run_polling()