"""Handlers: VOTE_METHOD, BARRIER_VOTE, DONE."""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.states import Survey
from app import backend_client as api
from app import keyboards as kb

logger = logging.getLogger(__name__)
router = Router()

VOTE_LABELS = {
    "electronic": "Электронно",
    "paper": "На бумаге",
    "abstain": "Не голосую",
}
BARRIER_LABELS = {"for": "За", "against": "Против", "undecided": "Не определился"}


def _format_premises_list(premises: list[dict]) -> str:
    lines = ["Ваши помещения:"]
    for p in premises:
        lines.append(f"  ✓ {p['display']}")
    return "\n".join(lines)


async def show_vote_method(msg: Message, state: FSMContext, edit: bool = False):
    sd = await state.get_data()
    premises = sd.get("user_premises", [])
    user_data = sd.get("user_data", {})

    text_lines = [_format_premises_list(premises), ""]
    text_lines.append("Как вы планируете голосовать на ОСС?")
    text_lines.append("")
    text_lines.append("Рекомендуем установить приложение «Электронный Дом» (mos.ru/ed) и убедиться, что видите там все свои помещения.")

    vf = user_data.get("vote_format")
    re = user_data.get("registered_in_ed")
    if vf:
        label = VOTE_LABELS.get(vf, vf)
        ed_note = ""
        if vf == "electronic":
            ed_note = ", В ЭД зарегистрированы" if re else ", В ЭД не зарегистрированы"
        text_lines.append(f"\nРанее вы отвечали: {label}{ed_note}✎")

    await state.set_state(Survey.VOTE_METHOD)
    text = "\n".join(text_lines)
    if edit:
        await msg.edit_text(text, reply_markup=kb.vote_method_kb())
    else:
        await msg.answer(text, reply_markup=kb.vote_method_kb())


@router.callback_query(F.data.startswith("vote:"), Survey.VOTE_METHOD)
async def cb_vote(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":", 1)[1]
    await callback.answer()
    uid = callback.from_user.id

    kwargs = {}
    if choice == "ed_plan":
        kwargs = {"vote_format": "electronic", "registered_in_ed": "false"}
    elif choice == "ed_ok":
        kwargs = {"vote_format": "electronic", "registered_in_ed": "true"}
    elif choice == "paper":
        kwargs = {"vote_format": "paper", "registered_in_ed": "false"}
    elif choice == "abstain":
        kwargs = {"vote_format": "abstain"}

    result = await api.update_answers(uid, **kwargs)
    if result.get("_status") == 429:
        await callback.message.edit_text("Слишком много отправок, попробуйте позже.")
        return

    sd = await state.get_data()
    ud = sd.get("user_data", {})
    ud.update(kwargs)
    await state.update_data(user_data=ud)

    await show_barrier_vote(callback.message, state, edit=True)


@router.callback_query(F.data == "back", Survey.VOTE_METHOD)
async def cb_back_vote(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = callback.from_user.id
    from app.handlers.premises import show_premises_overview
    await show_premises_overview(callback.message, state, uid, edit=True)


async def show_barrier_vote(msg: Message, state: FSMContext, edit: bool = False):
    sd = await state.get_data()
    user_data = sd.get("user_data", {})

    text_lines = [
        "Готовы поддержать схему размещения шлагбаумов?",
        "https://t.me/SILVERINFO/4304",
    ]
    bv = user_data.get("barrier_vote")
    if bv:
        text_lines.append(f"\nРанее вы отвечали: {BARRIER_LABELS.get(bv, bv)} ✎")

    await state.set_state(Survey.BARRIER_VOTE)
    text = "\n".join(text_lines)
    if edit:
        await msg.edit_text(text, reply_markup=kb.barrier_vote_kb())
    else:
        await msg.answer(text, reply_markup=kb.barrier_vote_kb())


@router.callback_query(F.data.startswith("barrier:"), Survey.BARRIER_VOTE)
async def cb_barrier(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":", 1)[1]
    await callback.answer()
    uid = callback.from_user.id

    result = await api.update_answers(uid, barrier_vote=choice)
    if result.get("_status") == 429:
        await callback.message.edit_text("Слишком много отправок, попробуйте позже.")
        return

    sd = await state.get_data()
    ud = sd.get("user_data", {})
    ud["barrier_vote"] = choice
    await state.update_data(user_data=ud)

    from app.handlers.contact import show_contact_manage
    await show_contact_manage(callback.message, state, edit=True)


@router.callback_query(F.data == "back", Survey.BARRIER_VOTE)
async def cb_back_barrier(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_vote_method(callback.message, state, edit=True)


async def show_done(msg: Message, state: FSMContext, edit: bool = False):
    sd = await state.get_data()
    premises = sd.get("user_premises", [])
    user_data = sd.get("user_data", {})

    lines = ["Спасибо! Ваши данные сохранены.\n", "Сводка:"]
    prem_list = ", ".join(p["display"] for p in premises) if premises else "—"
    lines.append(f"  Помещения: {prem_list}")

    vf = user_data.get("vote_format")
    re = user_data.get("registered_in_ed")
    if vf == "electronic":
        ed_status = "Да" if re == "true" or re is True else "Нет"
        lines.append(f'  Регистрация в "Электронном Доме": {ed_status}')
        lines.append(f"  Голосование: Электронно (Электронный Дом)")
    elif vf:
        lines.append(f"  Голосование: {VOTE_LABELS.get(vf, vf)}")

    bv = user_data.get("barrier_vote")
    if bv:
        lines.append(f"  Шлагбаумы: {BARRIER_LABELS.get(bv, bv)}")

    phone = user_data.get("phone")
    lines.append(f"  Телефон: {phone or '—'}")
    lines.append("\nЕсли что-то изменится — возвращайтесь: /start")

    await state.set_state(Survey.DONE)
    text = "\n".join(lines)
    if edit:
        await msg.edit_text(text, reply_markup=kb.done_kb())
    else:
        await msg.answer(text, reply_markup=kb.done_kb())


@router.callback_query(F.data == "edit_data", Survey.DONE)
async def cb_edit_from_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = callback.from_user.id
    from app.handlers.premises import show_premises_overview
    await show_premises_overview(callback.message, state, uid, edit=True)
