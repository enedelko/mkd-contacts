"""Handlers: IDLE, /start, /help, /cancel, /mydata, unrecognized."""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.states import Survey
from app import keyboards as kb

logger = logging.getLogger(__name__)
router = Router()

WELCOME = (
    "Этот бот помогает собрать голоса собственников\n"
    "для предстоящего Общего собрания собственников в ЖК Silver.\n\n"
    "Нам важно понять, набирается ли кворум — 2/3 голосов\n"
    "от общей площади дома.\n\n"
    "Если вы собственник помещения в этом доме — нажмите кнопку ниже."
)

HELP = (
    "/start — начать анкету\n"
    "/mydata — посмотреть свои данные\n"
    "/cancel — отменить текущий диалог\n"
    "/help — эта справка"
)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME, reply_markup=kb.idle_kb())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Диалог отменён.", reply_markup=kb.idle_kb())


@router.message(Command("mydata"))
async def cmd_mydata(message: Message, state: FSMContext):
    from app.handlers.mydata import show_my_data
    await show_my_data(message, state)


@router.callback_query(F.data == "owner")
async def cb_owner(callback: CallbackQuery, state: FSMContext):
    from app.handlers.premises import show_premises_overview
    await callback.answer()
    await show_premises_overview(callback.message, state, callback.from_user.id, edit=True)


@router.callback_query(F.data == "mydata")
async def cb_mydata(callback: CallbackQuery, state: FSMContext):
    from app.handlers.mydata import show_my_data
    await callback.answer()
    await show_my_data(callback.message, state, user_id=callback.from_user.id)


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(HELP)


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Диалог отменён.")
    await callback.message.answer(WELCOME, reply_markup=kb.idle_kb())


@router.callback_query(F.data == "close")
async def cb_close(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("До свидания! /start — чтобы начать заново.")
