import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# 🔹 Настройки
TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_ОТСЮДА")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://peacesellsshopping-bot.onrender.com")
PORT = int(os.getenv("PORT", "10000"))
ALLOWED_USERS = [431417737, 1117100895]

# 🔹 Логирование
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# 🔹 Проверка доступа
def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS


# 🔹 Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/start от {user_id}")

    if not is_allowed(user_id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    await update.message.reply_text("✅ Бот запущен и готов к работе!")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    logger.info(f"Сообщение от {user_id}: {text}")

    if not is_allowed(user_id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    await update.message.reply_text(f"Вы написали: {text}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")


# 🔹 Основной запуск
def main():
    logger.info("🚀 Запуск бота...")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.add_error_handler(error_handler)

    logger.info("🔗 Установка webhook...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
    )


if __name__ == "__main__":
    main()
