import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# ⬇️ Питання тільки для Hard Test
hard_questions = [
    {
        "text": "Яких елементів не вистачає на платі KeyPad?",
        "image": "images/keypad_missing.jpg",
        "options": [
            ("Холдер '+'", True),
            ("Світлодіод", True),
            ("Резистор", True),
            ("Холдер '-'", True)
        ]
    },
    # ➕ Додайте інші питання тут
]

load_dotenv()
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 710633503

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is running!"

@app.route("/ping")
def ping():
    return "OK", 200

Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

class QuizState(StatesGroup):
    question_index = State()
    selected_options = State()
    temp_selected = State()
    wrong_answers = State()
    current_options = State()
    last_message_id = State()

@dp.message(F.text == "/start")
async def start_cmd(message: types.Message, state: FSMContext):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("💪 Hard Test"))
    await message.answer("Вибери розділ:", reply_markup=keyboard)

@dp.message(F.text == "💪 Hard Test")
async def start_quiz(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QuizState.question_index)
    await state.update_data(
        question_index=0,
        selected_options=[],
        temp_selected=set(),
        wrong_answers=[]
    )
    await send_question(message, state)

async def send_question(msg_or_cb, state: FSMContext):
    data = await state.get_data()
    idx = data["question_index"]
    if idx >= len(hard_questions):
        await finish_quiz(msg_or_cb, state)
        return

    question = hard_questions[idx]
    options = list(enumerate(question["options"]))
    random.shuffle(options)

    selected = data.get("temp_selected", set())
    buttons = []
    for i, (label, _) in options:
        prefix = "✅ " if i in selected else "◻️ "
        buttons.append([InlineKeyboardButton(text=prefix + label, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        if data.get("last_message_id"):
            await bot.delete_message(msg_or_cb.chat.id, data["last_message_id"])
    except:
        pass

    if question.get("image"):
        sent = await bot.send_photo(
            msg_or_cb.chat.id,
            photo=open(question["image"], "rb"),
            caption=question["text"],
            reply_markup=keyboard
        )
    else:
        sent = await bot.send_message(msg_or_cb.chat.id, question["text"], reply_markup=keyboard)

    await state.update_data(last_message_id=sent.message_id, current_options=options)

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
    await send_question(callback, state)

@dp.callback_query(F.data == "confirm")
async def confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    temp = data.get("temp_selected", set())
    selected_options = data.get("selected_options", [])
    current_options = data.get("current_options", [])
    original_question = hard_questions[data["question_index"]]

    selected_texts = [current_options[i][0] for i in temp]
    final_indices = [i for i, (t, _) in enumerate(original_question["options"]) if t in selected_texts]
    selected_options.append(final_indices)

    await state.update_data(
        selected_options=selected_options,
        question_index=data["question_index"] + 1,
        temp_selected=set()
    )
    await send_question(callback, state)

async def finish_quiz(cb, state: FSMContext):
    data = await state.get_data()
    correct = 0
    wrongs = []
    for i, q in enumerate(hard_questions):
        correct_set = {j for j, (_, ok) in enumerate(q["options"]) if ok}
        user_set = set(data["selected_options"][i])
        if correct_set == user_set:
            correct += 1
        else:
            wrongs.append({"question": q["text"], "options": q["options"], "selected": list(user_set), "correct": list(correct_set)})

    await state.update_data(wrong_answers=wrongs)

    percent = round(correct / len(hard_questions) * 100)
    grade = "❌ Погано"
    if percent >= 90:
        grade = "📏 Відмінно"
    elif percent >= 70:
        grade = "👍 Добре"
    elif percent >= 50:
        grade = "👌 Задовільно"

    result = (
        "📊 *Результат тесту:*\n\n"
        f"✅ *Правильних відповідей:* {correct} з {len(hard_questions)}\n"
        f"📈 *Успішність:* {percent}%\n"
        f"🏆 *Оцінка:* {grade}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Пройти ще раз", callback_data="restart")]
    ])
    await cb.message.answer(result, parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data == "restart")
async def restart(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await start_cmd(callback.message, state)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
