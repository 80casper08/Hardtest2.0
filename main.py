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
from questions import hard_questions

load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
ADMIN_ID = 710633503

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
    wrong_answers = State()
    temp_selected = State()
    last_message_id = State()
    current_options = State()

def main_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="💪 Hard Test")]],
        resize_keyboard=True
    )

@dp.message(F.text == "💪 Hard Test")
async def start_quiz(message: types.Message, state: FSMContext):
    await state.set_state(QuizState.question_index)
    await state.update_data(
        question_index=0,
        selected_options=[],
        wrong_answers=[],
        temp_selected=set(),
    )

    await send_question(message, state)

async def send_question(message_or_callback, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    if index >= len(hard_questions):
        correct = 0
        wrongs = []
        for i, q in enumerate(hard_questions):
            correct_answers = {j for j, (_, is_correct) in enumerate(q["options"]) if is_correct}
            user_selected = set(data["selected_options"][i])
            if correct_answers == user_selected:
                correct += 1
            else:
                wrongs.append({
                    "question": q["text"],
                    "options": q["options"],
                    "selected": list(user_selected),
                    "correct": list(correct_answers)
                })

        await state.update_data(wrong_answers=wrongs)
        percent = round(correct / len(hard_questions) * 100)
        grade = "❌ Погано"
        if percent >= 90:
            grade = "💯 Відмінно"
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
            [InlineKeyboardButton(text="🔁 Пройти ще раз", callback_data="restart")],
            [InlineKeyboardButton(text="📋 Детальна інформація", callback_data="details")]
        ])

        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.answer(result, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await message_or_callback.answer(result, reply_markup=keyboard, parse_mode="Markdown")
        return

    question = hard_questions[index]
    text = question["text"]
    original_options = list(enumerate(question["options"]))
    random.shuffle(original_options)

    selected = data.get("temp_selected", set())
    buttons = []
    for i, (label, _) in original_options:
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

    await state.update_data(last_message_id=sent.message_id, current_options=original_options)

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
async def confirm_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("temp_selected", set())
    selected_options = data.get("selected_options", [])
    current_options = data.get("current_options")
    original_question = hard_questions[data["question_index"]]

    selected_texts = [current_options[i][0] for i in selected]
    final_indices = [i for i, (text, _) in enumerate(original_question["options"]) if text in selected_texts]

    selected_options.append(final_indices)

    await state.update_data(
        selected_options=selected_options,
        question_index=data["question_index"] + 1,
        temp_selected=set()
    )
    await send_question(callback, state)

@dp.callback_query(F.data == "details")
async def show_details(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    wrongs = data.get("wrong_answers", [])
    if not wrongs:
        await callback.message.answer("✅ Усі відповіді правильні!")
        return

    for item in wrongs:
        text = f"❌ *{item['question']}*\n"
        for idx, (opt_text, _) in enumerate(item["options"]):
            mark = "☑️" if idx in item["selected"] else "🔘"
            text += f"{mark} {opt_text}\n"
        selected_text = [item["options"][i][0] for i in item["selected"]] if item["selected"] else ["—"]
        correct_text = [item["options"][i][0] for i in item["correct"]]
        text += f"\n_Твоя відповідь:_ {', '.join(selected_text)}"
        text += f"\n_Правильна відповідь:_ {', '.join(correct_text)}"
        await callback.message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data == "restart")
async def restart_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Натисни ще раз '💪 Hard Test' для нового проходження.", reply_markup=main_keyboard())

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer("Натисни '💪 Hard Test' щоб почати:", reply_markup=main_keyboard())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


