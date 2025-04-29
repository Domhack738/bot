import logging
import time
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = "7933076784:AAE5rdtnxL44MBKCeC-xH7sA90dqN_VWTqk"
GROUP_ID = -1002317640685

# Хранилище данных
message_user_map = {}  # group_msg_id -> (user_id, number)
user_number_map = {}   # user_id -> number
user_rating_map = {}   # user_id -> rating
user_history_map = {}  # user_id -> list of (number, time, start_time)
user_queue_map = {}    # user_id -> queue position
user_placed_map = {}   # user_id -> set of placed numbers (новая переменная)
waiting_for_number = set()  # Список пользователей, которые ожидают ввода номера

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Проверка, является ли пользователь администратором
async def is_admin(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        chat_administrators = await context.bot.get_chat_administrators(GROUP_ID)
        admins_ids = [admin.user.id for admin in chat_administrators]
        return user_id in admins_ids
    except Exception as e:
        logger.error(f"Ошибка при проверке админа: {e}")
        return False

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Сдать номер", callback_data="submit_number"),
            InlineKeyboardButton("История номеров", callback_data="history"),
            InlineKeyboardButton("Очередь", callback_data="queue"),
            InlineKeyboardButton("Рейтинг", callback_data="rating"),
            InlineKeyboardButton("Реферальная система", callback_data="referral")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Добро пожаловать! Выберите опцию:", reply_markup=reply_markup)

# Главное меню
async def return_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Сдать номер", callback_data="submit_number"),
            InlineKeyboardButton("История номеров", callback_data="history"),
            InlineKeyboardButton("Очередь", callback_data="queue"),
            InlineKeyboardButton("Рейтинг", callback_data="rating"),
            InlineKeyboardButton("Реферальная система", callback_data="referral")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("Вы вернулись в главное меню", reply_markup=reply_markup)

# Сдать номер
async def handle_submit_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("Введите номер телефона (например, +79001112233):")
    # Помечаем пользователя как ожидающего номер
    user_id = update.callback_query.from_user.id
    waiting_for_number.add(user_id)

# История
async def handle_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    history = user_history_map.get(user_id, [])
    if not history:
        await update.callback_query.edit_message_text("📜 Ваша история пуста.")
        return
    history_text = "\n".join([f"{item[0]} - {item[1]} часов (поставлен {item[2]})" for item in history])
    keyboard = [[InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="main_menu")]]
    await update.callback_query.edit_message_text(f"📜 История номеров:\n{history_text}", reply_markup=InlineKeyboardMarkup(keyboard))

# Очередь
async def handle_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    queue_pos = user_queue_map.get(user_id, "Ваша очередь не определена.")
    keyboard = [[InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="main_menu")]]
    await update.callback_query.edit_message_text(f"📊 Ваша очередь: {queue_pos}", reply_markup=InlineKeyboardMarkup(keyboard))

# Рейтинг
async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    rating = user_rating_map.get(user_id, 0.20)
    keyboard = [[InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="main_menu")]]
    await update.callback_query.edit_message_text(f"⭐ Ваш рейтинг: {rating}", reply_markup=InlineKeyboardMarkup(keyboard))

# Реферальная система
async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("🔗 Реферальная система не реализована.")

# Получение номера (если пользователь пытается ввести номер)
async def handle_user_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in waiting_for_number:
        # Если пользователь не ожидает ввода номера, игнорируем его сообщение
        await update.message.reply_text("❗ Для сдачи номера используйте кнопку 'Сдать номер' в меню.")
        return

    number = update.message.text.strip()

    if not number.startswith('+') or not number[1:].isdigit():
        await update.message.reply_text("❗ Введите корректный номер (например, +79001112233).")
        return

    # Проверка, не был ли уже этот номер поставлен
    if user_id in user_placed_map and number in user_placed_map[user_id]:
        await update.message.reply_text("❌ Вы уже поставили этот номер.")
        return

    user_number_map[user_id] = number
    queue_pos = len(user_queue_map) + 1
    user_queue_map[user_id] = queue_pos

    sent_msg = await context.bot.send_message(
        chat_id=GROUP_ID,
        text=f"📲 Новый номер: {number}\nОтветьте на это сообщение кодом или фото."
    )

    message_user_map[sent_msg.message_id] = (user_id, number)

    current_time = int(time.time())
    user_history_map.setdefault(user_id, []).append((number, 0, current_time))

    user_rating_map.setdefault(user_id, 0.20)

    # Убираем пользователя из списка ожидания
    waiting_for_number.remove(user_id)

    await update.message.reply_text("✅ Номер отправлен. Ожидайте код от группы.")

# Ответы в группе
async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.reply_to_message
    if not reply or reply.message_id not in message_user_map:
        return

    user_id, number = message_user_map[reply.message_id]

    if not await is_admin(update.message.from_user.id, context):
        return

    keyboard = [
        [
            InlineKeyboardButton("🔁 Повторный код", callback_data="repeat"),
            InlineKeyboardButton("✅ Поставил номер", callback_data="placed")
        ],
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message.photo:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=update.message.photo[-1].file_id,
            reply_markup=reply_markup
        )
    elif update.message.text:
        await context.bot.send_message(
            chat_id=user_id,
            text=update.message.text,
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(chat_id=user_id, text="Получен ответ, но формат неизвестен.")

# Обработка кнопок
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    number = user_number_map.get(user_id)
    if not number:
        await query.edit_message_text("Номер не найден. Сначала отправьте номер.")
        return

    if query.data == "repeat":
        msg = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"🔁 Пользователь просит новый код для номера: {number}\nОтветьте на это сообщение."
        )
        message_user_map[msg.message_id] = (user_id, number)
        await query.edit_message_text("🔁 Запрос повторного кода отправлен в группу.")
    elif query.data == "placed":
        # Удаление пользователя из очереди
        if user_id in user_queue_map:
            del user_queue_map[user_id]

        # Обновление времени установки номера
        current_time = int(time.time())
        for i, (num, hours, start_time) in enumerate(user_history_map.get(user_id, [])):
            if num == number:
                user_history_map[user_id][i] = (num, hours, current_time)

        # Добавление номера в список поставленных номеров
        user_placed_map.setdefault(user_id, set()).add(number)

        await query.edit_message_text("✅ Спасибо! Номер подтверждён и удалён из очереди.")

# Запуск бота
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_user_number))
    app.add_handler(MessageHandler(filters.REPLY & filters.Chat(GROUP_ID), handle_group_reply))
    app.add_handler(CallbackQueryHandler(handle_submit_number, pattern="^submit_number$"))
    app.add_handler(CallbackQueryHandler(handle_history, pattern="^history$"))
    app.add_handler(CallbackQueryHandler(handle_queue, pattern="^queue$"))
    app.add_handler(CallbackQueryHandler(handle_rating, pattern="^rating$"))
    app.add_handler(CallbackQueryHandler(handle_referral, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(return_to_main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(handle_button, pattern="^(repeat|placed)$"))

    app.run_polling()

if __name__ == "__main__":
    main()
