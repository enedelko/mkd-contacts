"""Handlers: MY_DATA_VIEW, CONFIRM_FORGET."""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.states import Survey
from app import backend_client as api
from app import keyboards as kb

logger = logging.getLogger(__name__)
router = Router()

VOTE_LABELS = {"electronic": "Электронно", "paper": "На бумаге", "abstain": "Не голосую"}
BARRIER_LABELS = {"for": "За", "against": "Против", "undecided": "Не определился"}


async def show_my_data(msg: Message, state: FSMContext, user_id: int | None = None, edit: bool = False):
    uid = user_id or msg.chat.id
    data = await api.get_my_data(uid)
    premises = data.get("premises", [])

    if not premises:
        text = "У нас пока нет ваших данных."
        await state.set_state(Survey.MY_DATA_VIEW)
        if edit:
            await msg.edit_text(text, reply_markup=kb.my_data_empty_kb())
        else:
            await msg.answer(text, reply_markup=kb.my_data_empty_kb())
        return

    await state.update_data(tg_uid=uid, user_premises=premises, user_data=data)

    lines = ["Ваши данные в системе:\n"]
    prem_display = ", ".join(p["display"] for p in premises)
    lines.append(f"  Помещения: {prem_display}")

    vf = data.get("vote_format")
    re_ed = data.get("registered_in_ed")
    if vf == "electronic":
        ed_note = " (зарегистрированы в ЭД)" if (re_ed in ("true", "yes") or re_ed is True) else " (планируют установить ЭД)"
        lines.append(f"  Голосование: Электронно{ed_note}")
    elif vf:
        lines.append(f"  Голосование: {VOTE_LABELS.get(vf, vf)}")

    bv = data.get("barrier_vote")
    if bv:
        lines.append(f"  Шлагбаумы: {BARRIER_LABELS.get(bv, bv)}")

    phone = data.get("phone")
    lines.append(f"  Телефон: {phone or '—'}")
    lines.append("\nЧто хотите сделать?")

    text = "\n".join(lines)
    await state.set_state(Survey.MY_DATA_VIEW)
    if edit:
        await msg.edit_text(text, reply_markup=kb.my_data_view_kb())
    else:
        await msg.answer(text, reply_markup=kb.my_data_view_kb())


@router.callback_query(F.data == "edit_data", Survey.MY_DATA_VIEW)
async def cb_edit_data(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = callback.from_user.id
    from app.handlers.premises import show_premises_overview
    await show_premises_overview(callback.message, state, uid, edit=True)


@router.callback_query(F.data == "forget", Survey.MY_DATA_VIEW)
async def cb_forget(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    text = (
        "Вы уверены? Все ваши данные будут удалены из системы:\n"
        "помещения, ответы на вопросы, телефон, привязка Telegram.\n\n"
        "Это действие необратимо.\n"
        "В журнале аудита останется только запись о факте удаления."
    )
    await callback.message.edit_text(text, reply_markup=kb.confirm_forget_kb())
    await state.set_state(Survey.CONFIRM_FORGET)


# --- CONFIRM_FORGET ---

@router.callback_query(F.data == "forget_yes", Survey.CONFIRM_FORGET)
async def cb_forget_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = callback.from_user.id
    await api.forget(uid)
    await state.clear()
    await callback.message.edit_text("Все ваши данные удалены.")
    from app.handlers.start import WELCOME
    await callback.message.answer(WELCOME, reply_markup=kb.idle_kb())


@router.callback_query(F.data == "forget_cancel", Survey.CONFIRM_FORGET)
async def cb_forget_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_my_data(callback.message, state, user_id=callback.from_user.id, edit=True)
