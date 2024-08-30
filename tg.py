import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import F
import aiosqlite
from quiz_data import quiz_data
import sqlite3

# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)

# Замените "YOUR_BOT_TOKEN" на токен, который вы получили от BotFather
API_TOKEN = '7493932670:AAEe1gpUfVZRajoT12cg9Tp7A8jHFALgivM'

# Объект бота
bot = Bot(token=API_TOKEN)
# Диспетчер
dp = Dispatcher()

# Зададим имя базы данных
DB_NAME = 'quiz_bot.db'


def generate_options_keyboard(answer_options, right_answer):
  # Создаем сборщика клавиатур типа Inline
    builder = InlineKeyboardBuilder()

    # В цикле создаем 4 Inline кнопки, а точнее Callback-кнопки
    for option in answer_options:
        builder.add(types.InlineKeyboardButton(
            # Текст на кнопках соответствует вариантам ответов
            text=option,
            # Присваиваем данные для колбэк запроса.
            # Если ответ верный сформируется колбэк-запрос с данными 'right_answer'
            # Если ответ неверный сформируется колбэк-запрос с данными 'wrong_answer'
            callback_data="right_answer" if option == right_answer else "wrong_answer")
        )

    # Выводим по одной кнопке в столбик
    builder.adjust(1)
    return builder.as_markup()

@dp.callback_query(F.data == "right_answer")
async def right_answer(callback: types.CallbackQuery):
    # редактируем текущее сообщение с целью убрать кнопки (reply_markup=None)
    await save_result(callback.from_user.id, 'right_answer')
    current_question_index = await get_quiz_index(callback.from_user.id)
    quiz_data[current_question_index]['result'] = 'right_answer'
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )

    # Получение текущего вопроса для данного пользователя
    current_question_index = await get_quiz_index(callback.from_user.id)

    # Отправляем в чат сообщение, что ответ верный
    await callback.message.answer("Верно!")

    # Обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index)

    # Проверяем достигнут ли конец квиза
    if current_question_index < len(quiz_data):
        # Следующий вопрос
        await get_question(callback.message, callback.from_user.id)
    else:
        # Уведомление об окончании квиза
        await callback.message.answer("Это был последний вопрос. Квиз завершен!")


async def save_result(user_id, result):
    """Сохраняет результат пользователя в базу данных."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Проверяем, существует ли запись для данного пользователя
        exists = await db.execute('SELECT count(*) FROM results WHERE user_id = ?', (user_id,))

        if exists:
            # Если запись существует, обновляем её
            await db.execute('UPDATE results SET result = ? WHERE user_id = ?', (result, user_id))
        else:
            # В противном случае, вставляем новую запись
            await db.execute('INSERT INTO results (user_id, result) VALUES (?, ?)', (user_id, result))
        await db.commit()

async def get_results(user_id):
    """Возвращает результаты пользователя из базы данных."""
    results = []
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT * FROM results WHERE user_id = ?', (user_id, )) as cursor:
            results = await cursor.fetchall()
    return results
async def show_statistics(user_id, results):
    """Выводит статистику результатов пользователя."""
    total_correct = 0
    total_incorrect = 0
    for result in results:
        if result[1] == 'right_answer':
            total_correct += 1
        elif result[1] == 'wrong_answer':
            total_incorrect += 1
    percentage_correct = round((total_correct / (total_correct + total_incorrect)) * 100, 2)
    
    await bot.send_message(user_id, f"Ваша статистика: {total_correct} правильных ответов из {total_correct + total_incorrect}, что составляет {percentage_correct}%.")

@dp.callback_query(F.data == "wrong_answer")
async def wrong_answer(callback: types.CallbackQuery):
    # редактируем текущее сообщение с целью убрать кнопки (reply_markup=None)
    await save_result(callback.from_user.id, 'wrong_answer')
    current_question_index = await get_quiz_index(callback.from_user.id)
    quiz_data[current_question_index]['result'] = 'wrong_answer'
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )

    # Получение текущего вопроса для данного пользователя
    current_question_index = await get_quiz_index(callback.from_user.id)

    correct_option = quiz_data[current_question_index]['correct_option']

    # Отправляем в чат сообщение об ошибке с указанием верного ответа
    await callback.message.answer(f"Неправильно. Правильный ответ: {quiz_data[current_question_index]['options'][correct_option]}")

    # Обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index)

    # Проверяем достигнут ли конец квиза
    if current_question_index < len(quiz_data):
        # Следующий вопрос
        await get_question(callback.message, callback.from_user.id)
    else:
        # Уведомление об окончании квиза
        await callback.message.answer("Это был последний вопрос. Квиз завершен!")

# Хэндлер на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем сборщика клавиатур типа Reply
    builder = ReplyKeyboardBuilder()
    # Добавляем в сборщик одну кнопку
    builder.add(types.KeyboardButton(text="Начать игру"))
    # Прикрепляем кнопки к сообщению
    await message.answer("Добро пожаловать в квиз!", reply_markup=builder.as_markup(resize_keyboard=True))

async def get_question(message, user_id):

  # Запрашиваем из базы текущий индекс для вопроса
  current_question_index = await get_quiz_index(user_id)
  # Получаем индекс правильного ответа для текущего вопроса
  correct_index = quiz_data[current_question_index]['correct_option']
  # Получаем список вариантов ответа для текущего вопроса
  opts = quiz_data[current_question_index]['options']

  # Функция генерации кнопок для текущего вопроса квиза
  # В качестве аргументов передаем варианты ответов и значение правильного ответа (не индекс!)
  kb = generate_options_keyboard(opts, opts[correct_index])
  # Отправляем в чат сообщение с вопросом, прикрепляем сгенерированные кнопки
  await message.answer(f"{quiz_data[current_question_index]['question']}", reply_markup=kb)

async def new_quiz(message):
    # получаем id пользователя, отправившего сообщение
    user_id = message.from_user.id
    # сбрасываем значение текущего индекса вопроса квиза в 0
    current_question_index = 0
    await update_quiz_index(user_id, current_question_index)

    # запрашиваем новый вопрос для квиза
    await get_question(message, user_id)

async def get_quiz_index(user_id):
    # Подключаемся к базе данных
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем запись для заданного пользователя
        async with db.execute('SELECT question_index FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            # Возвращаем результат
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0

async def update_quiz_index(user_id, index):
    # Создаем соединение с базой данных (если она не существует, она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Вставляем новую запись или заменяем ее, если с данным user_id уже существует
        await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, question_index) VALUES (?, ?)', (user_id, index))
        # Сохраняем изменения
        await db.commit()
@dp.message(F.text=="Показать статистику")
@dp.message(Command("stat"))
async def show_my_stats(message: types.Message):
    results = await get_results(message.from_user.id)
    await show_statistics(message.from_user.id, results)
# Хэндлер на команды /quiz
@dp.message(F.text=="Начать игру")
@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message):
    # Отправляем новое сообщение без кнопок
    await message.answer(f"Давайте начнем квиз!")
    # Запускаем новый квиз
    await new_quiz(message)

async def create_table():
    # Создаем соединение с базой данных (если она не существует, то она будет создана)
    async with aiosqlite.connect('quiz_bot.db') as db:
        # Выполняем SQL-запрос к базе данных
        await db.execute('''CREATE TABLE IF NOT EXISTS quiz_state (user_id INTEGER PRIMARY KEY, question_index INTEGER)''')
        # Сохраняем изменения
        await db.commit()

# Запуск процесса поллинга новых апдейтов
async def main():
  # Запускаем создание таблицы базы данных
  await create_table()
  await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


    # C:/Users/Отец/AppData/Local/Programs/Python/Python312/python.exe c:/Users/Отец/Desktop/bot/tg.py