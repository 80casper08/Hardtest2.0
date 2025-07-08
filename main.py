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

load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class QuizState(StatesGroup):
    question_index = State()
    selected_options = State()
    questions = State()
    temp_selected = State()
    last_message_id = State()
    current_options = State()

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

@dp.callback_query(F.data.startswith("opt_"))
async def toggle_option(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split("_")[1])
    data = await state.get_data()
    current_options = dict(data.get("current_options", []))
    if index not in current_options:
        return await callback.answer("⚠️ Відповідь недійсна або застаріла.")

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
    current_options = dict(data.get("current_options", []))

    selected_texts = [current_options[i][0] for i in selected]
    original_question = data["questions"][data["question_index"]]
    final_indices = [i for i, (text, _) in enumerate(original_question["options"]) if text in selected_texts]
    selected_options.append(final_indices)

    await state.update_data(
        selected_options=selected_options,
        question_index=data["question_index"] + 1,
        temp_selected=set()
    )
    await send_question(callback, state)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
