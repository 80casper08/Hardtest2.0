import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Завантаження токена з .env
load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Стани FSM
class QuizState(StatesGroup):
    question_index = State()
    selected_options = State()
    questions = State()
    temp_selected = State()
    last_message_id = State()
    current_options = State()

# Питання
questions = [
    {
        "text": "Яких елементів не вистачає на платі KeyPad?",
        "image": "https://raw.githubusercontent.com/80casper08/Hardtest2.0/main/images/keypad.jpg",
        "options": [
            ("Холдер '-'", True),
            ("Холдер '+'", True),
            ("Резистор", False),
            ("Світлодіод", False),
        ]
    }
]

# Обробка /start
@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QuizState.question_index)
    await state.update_data(
        question_index=0,
        selected_options=[],
        questions=questions,
        temp_selected=set()
    )
    await send_question(message, state)

# Відправка питання
async def send_question(message_or_callback, state: FSMContext):
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]

    if index >= len(questions):
        await message_or_callback.answer("✅ Тест завершено!")
        return

    question = questions[index]
    text = question["text"]
    options = list(enumerate(question["options"]))
    random.shuffle(options)
    await state.update_data(current_options=options)

    selected = data.get("temp_selected", set())
    buttons = []
    for i, (label, _) in options:
        prefix = "✅ " if i in selected else "◻️ "
        buttons.append([InlineKeyboardButton(text=prefix + label, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if data.get("last_message_id"):
        try:
            await bot.delete_message(message_or_callback.chat.id, data["last_message_id"])
        except:
            pass

    if question.get("image"):
        sent = await bot.send_photo(
            message_or_callback.chat.id,
            photo=question["image"],
            caption=text,
            reply_markup=keyboard
        )
    else:
        sent = await bot.send_message(
            message_or_callback.chat.id,
            text,
            reply_markup=keyboard
        )

    await state.update_data(last_message_id=sent.message_id)

# Обробка вибору варіанту
@dp.callback_query(F.data.startswith("opt_"))
async def toggle_option(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split("_")[1])
    data = await state.get_data()
    current_options = data.get("current_options", [])
    option_indices = [i for i, _ in current_options]
    if index not in option_indices:
        return await callback.answer("⚠️ Відповідь недійсна або застаріла.")

    selected = data.get("temp_selected", set())
    if index in selected:
        selected.remove(index)
    else:
        selected.add(index)
    await state.update_data(temp_selected=selected)
    await send_question(callback, state)

# Обробка підтвердження
@dp.callback_query(F.data == "confirm")
async def confirm_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("temp_selected", set())
    selected_options = data.get("selected_options", [])
    current_options = data.get("current_options", [])
    selected_texts = [label for i, (label, _) in current_options if i in selected]

    original_question = data["questions"][data["question_index"]]
    final_indices = [i for i, (text, _) in enumerate(original_question["options"]) if text in selected_texts]
    selected_options.append(final_indices)

    await state.update_data(
        selected_options=selected_options,
        question_index=data["question_index"] + 1,
        temp_selected=set()
    )
    await send_question(callback, state)

# Flask для Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/ping")
def ping():
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# Старт бота
async def main():
    Thread(target=run_flask).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

