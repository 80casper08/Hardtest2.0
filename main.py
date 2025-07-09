import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class QuizState(StatesGroup):
    question_index = State()
    selected_options = State()
    temp_selected = State()

# Список питань
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
    # Додай ще питання у цьому ж форматі
]

@dp.message(F.text == "/start")
async def start_quiz(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QuizState.question_index)
    await state.update_data(
        question_index=0,
        selected_options=[],
        temp_selected=set()
    )
    await send_question(message, state)

async def send_question(target, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    if index >= len(questions):
        correct = 0
        for i, q in enumerate(questions):
            correct_answers = {j for j, (_, is_correct) in enumerate(q["options"]) if is_correct}
            user_selected = set(data["selected_options"][i])
            if correct_answers == user_selected:
                correct += 1
        total = len(questions)
        await bot.send_message(target.chat.id, f"📊 Результат тесту: {correct} з {total}")
        return

    question = questions[index]
    options = list(enumerate(question["options"]))
    await state.update_data(current_options=options)

    selected = data.get("temp_selected", set())
    buttons = []
    for i, (text, _) in options:
        prefix = "✅ " if i in selected else "◻️ "
        buttons.append([InlineKeyboardButton(text=prefix + text, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="Підтвердити", callback_data="confirm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if question.get("image"):
        await bot.send_photo(target.chat.id, photo=question["image"], caption=question["text"], reply_markup=keyboard)
    else:
        await bot.send_message(target.chat.id, text=question["text"], reply_markup=keyboard)

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
    await send_question(callback.message, state)

@dp.callback_query(F.data == "confirm")
async def confirm_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("temp_selected", set())
    selected_options = data.get("selected_options", [])
    current_options = data.get("current_options", [])
    selected_texts = [current_options[i][0] for i in selected]
    original_question = questions[data["question_index"]]
    final_indices = [i for i, (text, _) in enumerate(original_question["options"]) if text in selected_texts]

    selected_options.append(final_indices)
    await state.update_data(
        selected_options=selected_options,
        question_index=data["question_index"] + 1,
        temp_selected=set()
    )
    await send_question(callback.message, state)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
