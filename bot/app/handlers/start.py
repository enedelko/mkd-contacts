"""Handlers: IDLE, /start, /help, /cancel, /mydata, unrecognized."""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.states import Survey
from app import backend_client as api
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


def format_quorum_block(quorum: dict) -> str:
    """Формирует блок: % в ЭД, кворум, фраза про старт ОСС. Пустая строка если нет нужных полей."""
    ed_ratio = quorum.get("ed_ratio")
    quorum_reached = quorum.get("quorum_reached")
    if ed_ratio is None and quorum_reached is None:
        return ""
    parts = []
    if ed_ratio is not None:
        pct = round(float(ed_ratio) * 100, 1)
        parts.append(f"В Электронном Доме — {pct}% площади.")
    if quorum_reached is not None:
        parts.append(f"Кворум (2/3): {'да' if quorum_reached else 'ещё нет'}.")
    parts.append("ОСС стартуем после того, как будет набираться кворум.")
    return "По дому: " + " ".join(parts)


async def get_welcome_text() -> str:
    """Приветствие + блок кворума/ЭД при наличии данных с backend."""
    text = WELCOME
    quorum = await api.get_quorum()
    if quorum:
        block = format_quorum_block(quorum)
        if block:
            text = text + "\n\n" + block
    return text


ED_INSTRUCTION = (
    "Установка и настройка приложения «Электронный дом Москва»:\n"
    "1. Установить приложение «Электронный дом Москва».\n"
    "2. Зарегистрироваться/войти с использованием учётной записи mos.ru.\n"
    "3. Разрешить уведомления, чтобы не пропустить ОСС (не обязательно, но желательно).\n"
    "4. Проверить наличие всей собственности в ЭД и корректность статуса собственника: в нижнем меню — вкладка «Мой дом». Должны быть корректно указаны тип помещения (квартира, машиноместо и т.п.) и вы — как собственник.\n"
    "5. Если данные не подтверждены или статус собственника не отображается: «Настроить» → «Редактировать» → включить переключатель «В собственности» → «Сохранить».\n"
    "6. Если подтвердить собственность не получается — обратитесь в поддержку приложения."
)

HELP = (
    "Электронный Дом\n\n"
    + ED_INSTRUCTION
    + "\n\n"
    "/start — начать анкету\n"
    "/mydata — посмотреть свои данные\n"
    "/cancel — отменить текущий диалог\n"
    "/help — эта справка"
)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    text = await get_welcome_text()
    await message.answer(text, reply_markup=kb.idle_kb())


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
    text = await get_welcome_text()
    await callback.message.answer(text, reply_markup=kb.idle_kb())


@router.callback_query(F.data == "close")
async def cb_close(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("До свидания! /start — чтобы начать заново.")
