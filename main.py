

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

# 🌐 Flask-сервер для Render
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

# 🤖 Telegram
load_dotenv()
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class QuizState(StatesGroup):
    question_index = State()
    selected_options = State()
    temp_selected = State()
    current_message_id = State()

# ❓ Питання
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

@dp.message(F.text.startswith("/start"))
async def start_quiz(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QuizState.question_index)
    await state.update_data(
        question_index=0,
        selected_options=[],
        temp_selected=set()
    )
    await send_question(message.chat.id, state)

async def send_question(chat_id, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    if index >= len(questions):
        selected_all = data.get("selected_options", [])
        correct = 0
        for i, q in enumerate(questions):
            correct_indices = {j for j, (_, ok) in enumerate(q["options"]) if ok}
            user_selected = set(selected_all[i])
            if correct_indices == user_selected:
                correct += 1
        await bot.send_message(chat_id,
            f"📊 Результат тесту: {correct} з {len(questions)}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📋 Детальна інформація", callback_data="details")],
                    [InlineKeyboardButton(text="🔄 Пройти ще раз", callback_data="retry")]
                ]
            )
        )
        return

    question = questions[index]
    options = list(enumerate(question["options"]))
    await state.update_data(current_options=options, temp_selected=set())

    buttons = []
    for i, (text, _) in options:
        prefix = "◻️ "
        buttons.append([InlineKeyboardButton(text=prefix + text, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="Підтвердити", callback_data="confirm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # 🧹 Видаляємо попереднє повідомлення
    previous_id = data.get("current_message_id")
    if previous_id:
        try:
            await bot.delete_message(chat_id, previous_id)
        except:
            pass

    msg = await bot.send_photo(chat_id, photo=question["image"], caption=question["text"], reply_markup=keyboard)
    await state.update_data(current_message_id=msg.message_id)

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

    await bot.edit_message_reply_markup(
        chat_id=callback.message.chat.id,
        message_id=data["current_message_id"],
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "confirm")
async def confirm_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("temp_selected", set())
    selected_options = data.get("selected_options", [])

    final_indices = list(selected)

    selected_options.append(final_indices)
    new_index = data["question_index"] + 1
    await state.update_data(
        selected_options=selected_options,
        question_index=new_index,
        temp_selected=set()
    )
    await send_question(callback.message.chat.id, state)

@dp.callback_query(F.data == "details")
async def show_details(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_all = data.get("selected_options", [])
    text_blocks = []

    for i, q in enumerate(questions):
        correct_indices = {j for j, (_, ok) in enumerate(q["options"]) if ok}
        user_selected = set(selected_all[i])
        if correct_indices != user_selected:
            user_ans = [q["options"][j][0] for j in user_selected]
            correct_ans = [q["options"][j][0] for j in correct_indices]
            block = f"❓ *{q['text']}*\n" \
                    f"🔴 Ти вибрав: {', '.join(user_ans) if user_ans else 'нічого'}\n" \
                    f"✅ Правильно: {', '.join(correct_ans)}"
            text_blocks.append(block)

    if not text_blocks:
        await bot.send_message(callback.message.chat.id, "🥳 Всі відповіді правильні!")
    else:
        for block in text_blocks:
            await bot.send_message(callback.message.chat.id, block, parse_mode="Markdown")

@dp.callback_query(F.data == "retry")
async def restart_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(QuizState.question_index)
    await state.update_data(
        question_index=0,
        selected_options=[],
        temp_selected=set()
    )
    await send_question(callback.message.chat.id, state)

# 🚀 Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


