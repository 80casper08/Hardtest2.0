import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Flask-сервер для Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/ping")
def ping():
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_flask).start()

# Telegram
load_dotenv()
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class QuizState(StatesGroup):
    question_index = State()
    selected_options = State()
    temp_selected = State()
    message_ids = State()

# Питання
questions = [
    {
        "text": "1) Яких елементів не вистачає на платі KeyPad?",
        "image": "https://raw.githubusercontent.com/80casper08/Hardtest2.0/main/images/1.jpg",
        "options": [
            ("Холдер '-'", True),
            ("Холдер '+'", True),
            ("Резистор", False),
            ("Світлодіод", False)
        ]
    },
    {
        "text": "2) Яких елементів не вистачає на платі StreetSiren?",
        "image": "https://raw.githubusercontent.com/80casper08/Hardtest2.0/main/images/2.jpg",
        "options": [
            ("Антена", True),
            ("Кнопка", True),
            ("Світлодіод", False),
            ("Кварцовий резонатор", True)
        ]
    }
]

@dp.message(F.text == "/start")
async def start_quiz(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QuizState.question_index)
    await state.update_data(
        question_index=0,
        selected_options=[],
        temp_selected=set(),
        message_ids=[]
    )
    await send_question(message.chat.id, 0, state)

async def send_question(chat_id, index, state: FSMContext):
    if index >= len(questions):
        data = await state.get_data()
        selected_all = data.get("selected_options", [])
        correct = 0

        for i, q in enumerate(questions):
            correct_indices = {j for j, (_, ok) in enumerate(q["options"]) if ok}
            user_selected = set(selected_all[i])
            if correct_indices == user_selected:
                correct += 1

        await bot.send_message(chat_id, f"📊 Результат тесту: {correct} з {len(questions)}")
        return

    question = questions[index]
    options = list(enumerate(question["options"]))
    await state.update_data(current_options=options)

    selected = set()
    await state.update_data(temp_selected=selected)

    buttons = []
    for i, (text, _) in options:
        prefix = "✅ " if i in selected else "◻️ "
        buttons.append([InlineKeyboardButton(text=prefix + text, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="Підтвердити", callback_data="confirm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    msg = await bot.send_photo(chat_id, photo=question["image"], caption=question["text"], reply_markup=keyboard)

    # зберігаємо повідомлення, щоб не надсилати нове при кожному кліку
    data = await state.get_data()
    message_ids = data.get("message_ids", [])
    message_ids.append(msg.message_id)
    await state.update_data(message_ids=message_ids)

@dp.callback_query(F.data.startswith("opt_"))
async def toggle_option(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split("_")[1])
    data = await state.get_data()
    selected = data.get("temp_selected", set())

    if index in selected:
        selected.remove(index)
    else:
        selected.add(index)

    await state.update_data(temp_selected=selected)

    options = data["current_options"]
    buttons = []
    for i, (text, _) in options:
        prefix = "✅ " if i in selected else "◻️ "
        buttons.append([InlineKeyboardButton(text=prefix + text, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="Підтвердити", callback_data="confirm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # редагуємо попереднє повідомлення з фото
    message_ids = data["message_ids"]
    question = questions[data["question_index"]]
    await bot.edit_message_reply_markup(
        chat_id=callback.message.chat.id,
        message_id=message_ids[-1],
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "confirm")
async def confirm_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("temp_selected", set())
    selected_options = data.get("selected_options", [])
    selected_options.append(list(selected))
    await state.update_data(
        selected_options=selected_options,
        question_index=data["question_index"] + 1,
        temp_selected=set()
    )
    await send_question(callback.message.chat.id, data["question_index"] + 1, state)
