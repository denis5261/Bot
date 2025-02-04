import aiofiles
from gigachat import GigaChat
import os
import logging
import datetime
import json
import smtplib
import PyPDF2
import telebot
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TOKEN)
LOG_FILE = "requests_log.json"
REQUEST_LIMIT = 20

ADMIN_IDS = ['696933310']

# Функция загрузки логов
def load_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def send_broadcast(message):
    # Читаем словарь из логов
    logs_dict = load_logs()

    # Получаем сообщение от администратора
    broadcast_message = message.text.strip()

    sent_count = 0

    for user_id in logs_dict:
        try:
            bot.send_message(user_id, f"📢 *Сообщение от администратора:*\n\n{broadcast_message}", parse_mode="Markdown")
            sent_count += 1
        except Exception as e:
            logging.info(f"Не удалось отправить сообщение {user_id}: {e}")

    bot.send_message(message.chat.id, f"✅ Сообщение отправлено {sent_count} пользователям.")

# Функция сохранения логов
def save_logs(logs):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)

def admin_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("📊 Отправить файл со статистикой", "📢 Отправить сообщение всем пользователям")
    return keyboard


def gigachat(text):
    current_dir = os.path.dirname(os.path.abspath(__file__))  # Получаем текущую папку скрипта
    ca_bundle_file = os.path.join(current_dir, "russian_trusted_root_ca.cer")
    prompt = (
        "Ты — эксперт по медицинским анализам. "
        "Твоя задача — анализировать результаты анализов и выдавать понятные "
        "разъяснения. Твои ответы должны быть краткими, но информативными.\n\n"
        "Если тебе задают вопрос не по теме, то не отвечай на него"
    )


    full_text = prompt + text

    with GigaChat(
            credentials=os.getenv('API_KEY'),
            ca_bundle_file=ca_bundle_file) as giga:
        response = giga.chat(full_text)
        return response.choices[0].message.content


@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = str(message.from_user.id)
    logs = load_logs()

    if user_id not in logs:
        logs[user_id] = {"requests_today": 0, "last_request_date": ""}

    save_logs(logs)

    text = (
        "✨ Доброго времени суток, друзья! ✨\n\n"
        "🤖 Меня зовут *AnalysisObpproBot*.\n"
        "Я помогу расшифровать ваши анализы и объяснить результаты простым языком.\n\n"
        "📄 *Как воспользоваться ботом?*\n"
        "🔹 Прикрепите PDF-файл с анализами или вставьте результаты в чат.\n"
        "🔹 Я проанализирую их и предоставлю информационную справку.\n\n"
        "⚠ *Важно!* ⚠\n"
        "Этот бот не заменяет врача и предоставляет только информационные сведения.\n"
        "💬 История переписки *не сохраняется* и остаётся только в вашем диалоговом окне.\n\n"
        "🔐 *Пользуясь ботом, вы полностью принимаете политику обработки персональных данных:*\n"
        "(https://docs.google.com/document/d/1hOsAz2g--YBnQvQohbxa0Ybzb6oWH3aIAp796w7rgK4/edit?usp=sharing)"
    )
    if user_id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🔹 *Добро пожаловать в админ-панель!*", reply_markup=admin_keyboard(),
                         parse_mode="Markdown")
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == "📊 Отправить файл со статистикой")
def send_logs(message):
    if str(message.from_user.id) in ADMIN_IDS:
        file_path = LOG_FILE

        if os.path.exists(file_path):
            with open(file_path, "rb") as file:
                bot.send_document(message.chat.id, file)
        else:
            bot.send_message(message.chat.id, "❌ Файл статистики не найден.")
    else:
        bot.send_message(message.chat.id, "⛔ У вас нет прав доступа!")

@bot.message_handler(func=lambda message: message.text == "📢 Отправить сообщение всем пользователям")
def request_broadcast_message(message):
    if str(message.from_user.id) in ADMIN_IDS:
        bot.send_message(message.chat.id, "🔑 Введите сообщение для рассылки всем пользователям:")
        bot.register_next_step_handler(message, send_broadcast)
    else:
        bot.send_message(message.chat.id, "⛔ У вас нет прав доступа!")

# Обработчик загрузки PDF
@bot.message_handler(content_types=["document"])
def handle_pdf(message):
    user_id = str(message.from_user.id)
    logs = load_logs()

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if logs[user_id]["last_request_date"] != today:
        logs[user_id]["requests_today"] = 0
        logs[user_id]["last_request_date"] = today

    if logs[user_id]["requests_today"] >= REQUEST_LIMIT:
        bot.send_message(message.chat.id,
                         "❌ Вы достигли лимита запросов (20 в день). Пишите на potyy@ya.ru для увеличения.")
        return

    logs[user_id]["requests_today"] += 1
    save_logs(logs)

    document = message.document
    file_info = bot.get_file(document.file_id)
    file_path = file_info.file_path
    downloaded_file = bot.download_file(file_path)

    temp_pdf_path = f"temp_{user_id}.pdf"
    with open(temp_pdf_path, "wb") as f:
        f.write(downloaded_file)

    try:
        with open(temp_pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

        bot.send_message(message.chat.id, "📄 Анализы загружены. Обрабатываю данные...")
        result_text = f"🔎 Расшифровка анализов:\n\n{gigachat(text)}...\n\nБЛАГОДАРИМ ЗА ДОВЕРИЕ!"
        bot.send_message(message.chat.id, result_text)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка обработки PDF. Попробуйте другой файл.")
        logging.error(f"Ошибка чтения PDF: {e}")

    finally:
        os.remove(temp_pdf_path)


# Обработчик текстовых данных
@bot.message_handler(content_types=["text"])
def handle_text(message):
    user_id = str(message.from_user.id)
    logs = load_logs()

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if logs[user_id]["last_request_date"] != today:
        logs[user_id]["requests_today"] = 0
        logs[user_id]["last_request_date"] = today

    if logs[user_id]["requests_today"] >= REQUEST_LIMIT:
        bot.send_message(message.chat.id,
                         "❌ Вы достигли лимита запросов (20 в день). Пишите на potyy@ya.ru для увеличения.")
        return

    logs[user_id]["requests_today"] += 1
    save_logs(logs)

    bot.send_message(message.chat.id, "📄 Обрабатываю данные...")
    result_text = f"🔎 Расшифровка анализов:\n\n{gigachat(text=message.text)}...\n\nБЛАГОДАРИМ ЗА ДОВЕРИЕ!"
    bot.send_message(message.chat.id, result_text)


# Запуск бота
if __name__ == "__main__":
    bot.polling(none_stop=True)







# import os
# import json
# import logging
# import datetime
# import asyncio
# from aiogram import Bot, Dispatcher, types
# from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
# from aiogram.filters import Command
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.storage.memory import MemoryStorage
# from aiogram.client.default import DefaultBotProperties
# from aiogram.filters import StateFilter
# from dotenv import load_dotenv
# import PyPDF2
# from gigachat import GigaChat
#
# load_dotenv()
# TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# API_KEY = os.getenv("API_KEY")
# LOG_FILE = "requests_log.json"
# REQUEST_LIMIT = 20
# ADMIN_IDS = {'696933310'}
#
# logging.basicConfig(level=logging.INFO)
#
# bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
# dp = Dispatcher(storage=MemoryStorage())
#
#
# # Функция загрузки логов
# async def load_logs():
#     if os.path.exists(LOG_FILE):
#         async with aiofiles.open(LOG_FILE, "r", encoding="utf-8") as f:
#             return json.loads(await f.read())
#     return {}
#
#
# # Функция сохранения логов
# async def save_logs(logs):
#     async with aiofiles.open(LOG_FILE, "w", encoding="utf-8") as f:
#         await f.write(json.dumps(logs, indent=4, ensure_ascii=False))
#
#
# # Клавиатура для админа
# # def admin_keyboard():
# #     keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyb)
# #     keyboard.row("📊 Отправить файл со статистикой", "📢 Отправить сообщение всем пользователям")
# #     return keyboard
#
# def admin_keyboard():
#     keyboard = [
#         [KeyboardButton(text="📊 Отправить файл со статистикой")],
#         [KeyboardButton(text="📢 Отправить сообщение всем пользователям")],
#     ]
#     return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
#
#
# # Функция взаимодействия с GigaChat
# async def gigachat(text):
#     current_dir = os.path.dirname(os.path.abspath(__file__))  # Получаем текущую папку скрипта
#     ca_bundle_file = os.path.join(current_dir, "russian_trusted_root_ca.cer")
#     prompt = ("Ты — эксперт по медицинским анализам. "
#               "Твоя задача — анализировать результаты анализов и выдавать понятные "
#               "разъяснения. Твои ответы должны быть краткими, но информативными.")
#     full_text = prompt + text
#     with GigaChat(credentials=API_KEY, ca_bundle_file=ca_bundle_file) as giga:
#         response = giga.chat(full_text)
#         return response.choices[0].message.content
#
# @dp.message(Command("start"))
# async def send_welcome(message: types.Message):
#     user_id = str(message.from_user.id)
#     logs = await load_logs()
#
#     if user_id not in logs:
#         logs[user_id] = {"requests_today": 0, "last_request_date": ""}
#     await save_logs(logs)
#
#     text = ("✨ Доброго времени суток, друзья! ✨\n\n"
#             "🤖 Меня зовут *AnalysisObpproBot*.\n"
#             "Я помогу расшифровать ваши анализы и объяснить результаты простым языком.\n\n"
#             "📄 *Как воспользоваться ботом?*\n"
#             "🔹 Прикрепите PDF-файл с анализами или вставьте результаты в чат.\n"
#             "🔹 Я проанализирую их и предоставлю информационную справку.\n\n"
#             "⚠ *Важно!* ⚠\n"
#             "Этот бот не заменяет врача и предоставляет только информационные сведения.\n"
#             "💬 История переписки *не сохраняется* и остаётся только в вашем диалоговом окне.")
#
#     if user_id in ADMIN_IDS:
#         await message.answer("🔹 *Добро пожаловать в админ-панель!*", reply_markup=admin_keyboard())
#     await message.answer(text)
#
#
# @dp.message(lambda message: message.text == "📊 Отправить файл со статистикой")
# async def send_logs(message: types.Message):
#     if str(message.from_user.id) in ADMIN_IDS:
#         if os.path.exists(LOG_FILE):
#             await message.answer_document(types.FSInputFile(LOG_FILE))
#         else:
#             await message.answer("❌ Файл статистики не найден.")
#     else:
#         await message.answer("⛔ У вас нет прав доступа!")
#
#
# @dp.message(lambda message: message.text == "📢 Отправить сообщение всем пользователям")
# async def request_broadcast_message(message: types.Message, state: FSMContext):
#     if str(message.from_user.id) in ADMIN_IDS:
#         await message.answer("🔑 Введите сообщение для рассылки всем пользователям:")
#         await state.set_state("broadcast")
#     else:
#         await message.answer("⛔ У вас нет прав доступа!")
#
#
# @dp.message(Command("broadcast"))
# async def send_broadcast(message: types.Message, state: FSMContext):
#     logs_dict = await load_logs()
#     broadcast_message = message.text.strip()
#     sent_count = 0
#
#     for user_id in logs_dict:
#         try:
#             await bot.send_message(user_id, f"📢 *Сообщение от администратора:*\n\n{broadcast_message}")
#             sent_count += 1
#         except Exception as e:
#             logging.info(f"Не удалось отправить сообщение {user_id}: {e}")
#     await message.answer(f"✅ Сообщение отправлено {sent_count} пользователям.")
#     await state.clear()
#
#
# @dp.message(lambda message: message.document)
# async def handle_pdf(message: types.Message):
#     user_id = str(message.from_user.id)
#     logs = await load_logs()
#     today = datetime.datetime.now().strftime("%Y-%m-%d")
#
#     if logs[user_id]["last_request_date"] != today:
#         logs[user_id]["requests_today"] = 0
#         logs[user_id]["last_request_date"] = today
#
#     if logs[user_id]["requests_today"] >= REQUEST_LIMIT:
#         await message.answer("❌ Вы достигли лимита запросов (20 в день). Пишите на potyy@ya.ru для увеличения.")
#         return
#
#     logs[user_id]["requests_today"] += 1
#     await save_logs(logs)
#
#     document = message.document
#     file = await bot.download(document)
#
#     with open(f"temp_{user_id}.pdf", "wb") as f:
#         f.write(file.read())
#
#     try:
#         with open(f"temp_{user_id}.pdf", "rb") as f:
#             reader = PyPDF2.PdfReader(f)
#             text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
#
#         await message.answer("📄 Анализы загружены. Обрабатываю данные...")
#         result_text = f"🔎 Расшифровка анализов:\n\n{await gigachat(text)}...\n\nБЛАГОДАРИМ ЗА ДОВЕРИЕ!"
#         await message.answer(result_text)
#
#     except Exception as e:
#         await message.answer("❌ Ошибка обработки PDF. Попробуйте другой файл.")
#         logging.error(f"Ошибка чтения PDF: {e}")
#
#     finally:
#         os.remove(f"temp_{user_id}.pdf")
#
#
# async def main():
#     await dp.start_polling(bot)
#
#
# if __name__ == "__main__":
#     asyncio.run(main())



