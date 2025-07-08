import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv

from hard_questions import hard_questions  # ⚠️ окремий файл із питаннями

load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=Token)
dp = Dispatcher(storage=MemoryStorage())

class QuizState(StatesGroup):
    index = State()
    selected = State()
    results = State()
    temp = State()
    options_map = State()
    last_message_id = State()

@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QuizState.index)
    await state.update_data(
        index=0,
        selected=[],
        results=[],
        temp=set()
    )
    await send_question(message, state)

async def send_question(msg_or_cb, state: FSMContext):
    data = await state.get_data()
    index = data["index"]
    if index >= len(hard_questions):
        await show_result(msg_or_cb, state)
        return

    q = hard_questions[index]
    options = list(enumerate(q["options"]))
    random.shuffle(options)
    await state.update_data(options_map=options)

    buttons = []
    for i, (text, _) in options:
        prefix = "✅ " if i in data.get("temp", set()) else "◻️ "
        buttons.append([InlineKeyboardButton(text=prefix + text, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="Підтвердити ✅", callback_data="confirm")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    if data.get("last_message_id"):
        try:
            await bot.delete_message(msg_or_cb.chat.id, data["last_message_id"])
        except:
            pass

    if q.get("image"):
        photo = types.FSInputFile(q["image"])
        sent = await bot.send_photo(msg_or_cb.chat.id, photo=photo, caption=q["text"], reply_markup=markup)
    else:
        sent = await bot.send_message(msg_or_cb.chat.id, text=q["text"], reply_markup=markup)

    await state.update_data(last_message_id=sent.message_id)

@dp.callback_query(F.data.startswith("opt_"))
async def toggle_opt(callback: CallbackQuery, state: FSMContext):
    i = int(callback.data.split("_")[1])
    data = await state.get_data()
    temp = data.get("temp", set())
    temp ^= {i}
    await state.update_data(temp=temp)
    await send_question(callback, state)

@dp.callback_query(F.data == "confirm")
async def confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    temp = data.get("temp", set())
    options_map = data["options_map"]
    q = hard_questions[data["index"]]

    selected_texts = [options_map[i][0] for i in temp]
    correct_indexes = [i for i, (t, ok) in enumerate(q["options"]) if ok]
    correct_texts = [q["options"][i][0] for i in correct_indexes]

    is_correct = set(selected_texts) == set(correct_texts)
    data["results"].append((q["text"], selected_texts, correct_texts, is_correct))
    await state.update_data(
        index=data["index"] + 1,
        temp=set(),
        results=data["results"]
    )
    await send_question(callback, state)

async def show_result(source, state: FSMContext):
    data = await state.get_data()
    results = data["results"]
    correct = sum(1 for _, _, _, ok in results if ok)
    percent = round(correct / len(results) * 100)
    grade = "❌ Погано"
    if percent >= 90: grade = "💯 Відмінно"
    elif percent >= 70: grade = "👍 Добре"
    elif percent >= 50: grade = "👌 Задовільно"

    text = f"📊 *Результат:*\n\n✅ Правильних: {correct}/{len(results)}\n📈 Успішність: {percent}%\n🏆 Оцінка: {grade}"
    await source.message.answer(text, parse_mode="Markdown")

    for q_text, selected, correct, ok in results:
        mark = "✅" if ok else "❌"
        msg = f"{mark} *{q_text}*\n_Твоя відповідь:_ {', '.join(selected) if selected else '—'}\n_Правильна:_ {', '.join(correct)}"
        await source.message.answer(msg, parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


