import os
import logging
import datetime
import time

import PyPDF2
from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram import Bot, Dispatcher, types, filters, F
from aiogram.types import FSInputFile
import asyncio
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from settings import TOKEN, ADMIN_IDS, LOG_FILE, REQUEST_LIMIT_pdf, REQUEST_LIMIT_mes
from utils import load_logs, save_logs, load_prompt, save_prompt, refact_res_mes, gigachat

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

class Form(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_send_message = State()

def admin_keyboard():
    # Создаем клавиатуру с явным указанием поля `keyboard`
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            # Первая строка кнопок
            [
                KeyboardButton(text="📊 Отправить файл со статистикой"),
                KeyboardButton(text="📢 Отправить сообщение всем пользователям"),
            ],
            # Вторая строка кнопок
            [
                KeyboardButton(text="🤖 Изменить промпт"),
            ],
        ],
        resize_keyboard=True  # Автоматическое изменение размера клавиатуры
    )
    return keyboard

@dp.message(filters.command.Command('start'))
async def send_welcome(message: types.Message):
    user_id = str(message.from_user.id)
    logs = load_logs()
    if user_id in ADMIN_IDS:
        await message.answer("✨ADMIN панель доступна!✨", reply_markup=admin_keyboard())

    if user_id not in logs:
        logs[user_id] = {"Username": message.from_user.username, "requests_today_mes": 0, "requests_today_pdf": 0, "last_request_date": ""}
    save_logs(logs)

    text = ("✨ Доброго времени суток, друзья! ✨\n\n"
            "🤖 Меня зовут Расшифровщик медицинских анализов\n"
            "Я могу расшифровать ваши анализы, показать не просто цифры!\n\n"
            "📄 Отправьте свои исследовательские данные или анализы в формате PDF или в виде сообщения, и уже через несколько секунд получите готовый результат.\n"
            "⚠ Важно! ⚠\n"
            "Напоминаю, что я не заменяю врача, а предоставляю только информационную услугу.\n"
            "🔐 Пользуясь ботом, вы полностью принимаете политику обработки персональных данных:\n"
            "[Политика обработки](https://docs.google.com/document/d/1hOsAz2g--YBnQvQohbxa0Ybzb6oWH3aIAp796w7rgK4)\n"
            "❌ Действует лимит: по 5 PDF исследований в день."
            )
    await message.answer(text)


@dp.message(F.text == "📊 Отправить файл со статистикой")
async def send_logs(message: types.Message):
    # Проверка, является ли пользователь администратором
    if str(message.from_user.id) in ADMIN_IDS:
        # Проверка существования файла
        if os.path.exists(LOG_FILE):
            # Отправка файла
            await message.answer_document(document=FSInputFile(LOG_FILE))
        else:
            await message.answer("❌ Файл статистики не найден.")
    else:
        await message.answer("⛔ У вас нет прав доступа!")


@dp.message(F.text == "📢 Отправить сообщение всем пользователям")
async def request_broadcast_message(message: types.Message, state: FSMContext):
    if str(message.from_user.id) in ADMIN_IDS:
        markup = InlineKeyboardBuilder()
        markup.button(text="✅ Да", callback_data="confirm_prompt")
        markup.button(text="🚫 Отмена", callback_data="cancel_prompt")
        await message.answer("🔑 Введите сообщение для рассылки всем пользователям:")
        await state.set_state(Form.waiting_for_send_message)
        #dp.register_message_handler(send_broadcast, state=None)
    else:
        await message.answer("⛔ У вас нет прав доступа!")



@dp.message(F.text == "🤖 Изменить промпт")
async def change_prompt(message: types.Message):
    markup = InlineKeyboardBuilder()
    markup.button(text="✅ Да", callback_data="confirm_prompt")
    markup.button(text="🚫 Отмена", callback_data="cancel_prompt")

    await message.answer(text=f"✅Установленный промпт:\n{load_prompt()}\n\nХотите изменить его?", reply_markup=markup.as_markup())


@dp.message(Form.waiting_for_prompt)
async def process_new_prompt(message: types.Message, state: FSMContext):

    await message.answer(f"✅ {save_prompt(message)}")

    await state.clear()


@dp.message(Form.waiting_for_send_message)
async def process_send_all_users_message(message: types.Message, state: FSMContext):
    await state.update_data(message_text=message.text)
    markup = InlineKeyboardBuilder()
    markup.button(text="✅ Да", callback_data="confirm_message_all_users")
    markup.button(text="🚫 Отмена", callback_data="cancel_message_all_users")
    await message.answer(f"Отправить сообщение '{message.text}' всем пользователям?", reply_markup=markup.as_markup())


@dp.callback_query(F.data == "confirm_message_all_users")
async def confirm_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    await send_broadcast(callback_query.message, state)
    await callback_query.message.edit_reply_markup(reply_markup=None)
    #await state.clear()


@dp.callback_query(F.data == "cancel_message_all_users")
async def confirm_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer('🚫 Действие отменено')
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await state.clear()


@dp.callback_query(F.data == "confirm_prompt")
async def confirm_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    # Ответ на нажатие "✅ Да"
    await callback_query.answer()
    await callback_query.message.answer("📩 Пожалуйста, отправьте новый промпт:")

    # Убираем кнопки после ответа
    await callback_query.message.edit_reply_markup(reply_markup=None)

    # Переводим бота в состояние ожидания нового промпта
    await state.set_state(Form.waiting_for_prompt)


@dp.callback_query(F.data == "cancel_prompt")
async def cancel_prompt(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Изменение промпта отменено.")

    # Убираем кнопки после ответа
    await callback_query.message.edit_reply_markup(reply_markup=None)

async def send_broadcast(message: types.Message, state: FSMContext):
    data = await state.get_data()
    message_text = data.get("message_text")
    logs_dict = load_logs()
    sent_count = 0

    for user_id in logs_dict:
        try:
            await bot.send_message(user_id, f"{message_text}")
            sent_count += 1
        except Exception as e:
            logging.info(f"Не удалось отправить сообщение {user_id}: {e}")

    await message.answer(f"✅ Сообщение отправлено {sent_count} пользователям.")
    await state.clear()


@dp.message(F.document)
async def handle_pdf(message: types.Message):
    user_id = str(message.from_user.id)
    logs = load_logs()
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    if user_id not in logs:
        logs[user_id] = {"Username": message.from_user.username, "requests_today_mes": 0, "requests_today_pdf": 0, "last_request_date": ""}

    if logs[user_id]["last_request_date"] != today:
        logs[user_id]["requests_today_pdf"] = 0
        logs[user_id]["last_request_date"] = today

    if logs[user_id]["requests_today_pdf"] >= REQUEST_LIMIT_pdf:
        await message.answer("❌ Ваш сегодняшний лимит исчерпан.")
        return

    if not logs[user_id]['Username']:
        logs[user_id]['Username'] = message.from_user.username

    if user_id not in ADMIN_IDS:
        logs[user_id]["requests_today_pdf"] += 1
    save_logs(logs)

    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path
    downloaded_file = await bot.download_file(file_path)
    temp_pdf_path = f"temp_{user_id}.pdf"

    with open(temp_pdf_path, "wb") as f:
        f.write(downloaded_file.read())

    try:
        with open(temp_pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

        await message.answer("📄 Документ загружен. Обрабатываю данные...")
        result_text = f"{gigachat(text, load_prompt())}"
        await message.answer(refact_res_mes(result_text))
    except Exception as e:
        await message.answer("❌ Ошибка обработки PDF. Попробуйте другой файл.")
        logging.error(f"Ошибка чтения PDF: {e}")
    finally:
        os.remove(temp_pdf_path)


@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = str(message.from_user.id)
    logs = load_logs()
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    if user_id not in logs:
        logs[user_id] = {"Username": message.from_user.username, "requests_today_mes": 0, "requests_today_pdf": 0, "last_request_date": ""}

    if logs[user_id]["last_request_date"] != today:
        logs[user_id]["requests_today_mes"] = 0
        logs[user_id]["last_request_date"] = today

    if logs[user_id]["requests_today_mes"] >= REQUEST_LIMIT_mes:
        await message.answer("❌ Ваш сегодняшний лимит исчерпан.")
        return

    if not logs[user_id]['Username']:
        logs[user_id]['Username'] = message.from_user.username

    if user_id not in ADMIN_IDS:
        logs[user_id]["requests_today_mes"] += 1
    save_logs(logs)

    await message.answer("📄 Обрабатываю данные...")
    result_text = f"{gigachat(text=message.text, prompt=load_prompt())}"
    await message.answer(refact_res_mes(result_text))


async def main():
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print(f"Ошибка: {e}, перезапуск через 10 секунд...")
            time.sleep(10)

asyncio.run(main())
