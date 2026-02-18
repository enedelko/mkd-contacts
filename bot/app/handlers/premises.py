"""Handlers: PREMISES_OVERVIEW, ENTER_PREMISE, DISAMBIGUATE, CONFIRM_PREMISE,
OFFER_PARKING_STORAGE, OFFER_MORE, REMOVE_PREMISE, CONFIRM_REMOVE_PREMISE."""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.states import Survey
from app import backend_client as api
from app import keyboards as kb

logger = logging.getLogger(__name__)
router = Router()

APARTMENT_TYPES = {"Квартира", "Офис (апартаменты)"}


async def show_premises_overview(msg: Message, state: FSMContext, user_id: int | None = None, edit: bool = False):
    uid = user_id or msg.chat.id
    data = await api.get_my_data(uid)
    premises = data.get("premises", [])
    await state.update_data(tg_uid=uid, user_premises=premises, user_data=data)

    if not premises:
        text = (
            "Пока что у нас нет данных о ваших помещениях.\n"
            "Какая у вас квартира или другое помещение (апартаменты, машиноместо, кладовка)?\n"
            "Введите номер, например: кв.945"
        )
        await state.set_state(Survey.PREMISES_OVERVIEW)
        if edit:
            await msg.edit_text(text, reply_markup=kb.premises_overview_new_kb())
        else:
            await msg.answer(text, reply_markup=kb.premises_overview_new_kb())
    else:
        lines = ["Ваши помещения:"]
        for p in premises:
            lines.append(f"  • {p['display']}")
        lines.append("")
        lines.append("Пришлите номер помещения для добавления (например, мм.913) или переходите к вопросам по ОСС")
        await state.set_state(Survey.PREMISES_OVERVIEW)
        if edit:
            await msg.edit_text("\n".join(lines), reply_markup=kb.premises_overview_existing_kb())
        else:
            await msg.answer("\n".join(lines), reply_markup=kb.premises_overview_existing_kb())


@router.message(Survey.PREMISES_OVERVIEW)
async def premises_text_input(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.strip():
        return
    uid = message.from_user.id
    matches = await api.resolve_premise(text, str(uid))
    if not matches:
        await message.answer("Не найдено. Попробуйте ещё раз.")
        return
    if len(matches) == 1:
        m = matches[0]
        await state.update_data(pending_premise=m)
        await message.answer(
            f"{m['display']}\nВерно?",
            reply_markup=kb.confirm_premise_kb(m["premise_id"]),
        )
        await state.set_state(Survey.CONFIRM_PREMISE)
    else:
        await state.update_data(disambiguate_matches=matches)
        await message.answer("Найдено несколько вариантов:", reply_markup=kb.disambiguate_kb(matches))
        await state.set_state(Survey.DISAMBIGUATE)


@router.callback_query(F.data == "add_premise", Survey.PREMISES_OVERVIEW)
async def cb_add_premise(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Введите номер помещения (например, кв. 911)")


@router.callback_query(F.data == "to_questions")
async def cb_to_questions(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from app.handlers.survey import show_vote_method
    await show_vote_method(callback.message, state, edit=True)


@router.callback_query(F.data == "remove_premise")
async def cb_remove_premise(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    sd = await state.get_data()
    premises = sd.get("user_premises", [])
    if not premises:
        await callback.message.edit_text("У вас нет помещений для удаления.")
        return
    await callback.message.edit_text("Какое помещение убрать из списка?", reply_markup=kb.remove_premise_kb(premises))
    await state.set_state(Survey.REMOVE_PREMISE)


# --- DISAMBIGUATE ---

@router.callback_query(F.data.startswith("pick:"), Survey.DISAMBIGUATE)
async def cb_pick_premise(callback: CallbackQuery, state: FSMContext):
    premise_id = callback.data.split(":", 1)[1]
    await callback.answer()
    sd = await state.get_data()
    matches = sd.get("disambiguate_matches", [])
    chosen = next((m for m in matches if m["premise_id"] == premise_id), None)
    if not chosen:
        await callback.message.edit_text("Ошибка, попробуйте ещё раз.")
        await state.set_state(Survey.PREMISES_OVERVIEW)
        return
    await state.update_data(pending_premise=chosen)
    await callback.message.edit_text(f"{chosen['display']}\nВерно?", reply_markup=kb.confirm_premise_kb(premise_id))
    await state.set_state(Survey.CONFIRM_PREMISE)


@router.callback_query(F.data == "retry_premise", Survey.DISAMBIGUATE)
async def cb_retry(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = callback.from_user.id
    await show_premises_overview(callback.message, state, uid, edit=True)


# --- CONFIRM_PREMISE ---

@router.callback_query(F.data.startswith("confirm_yes:"), Survey.CONFIRM_PREMISE)
async def cb_confirm_yes(callback: CallbackQuery, state: FSMContext):
    premise_id = callback.data.split(":", 1)[1]
    await callback.answer()
    uid = callback.from_user.id
    result = await api.add_premise(uid, premise_id)
    status = result.get("_status", 500)
    if status == 409:
        await callback.message.edit_text("По этому помещению уже достаточно записей.")
        await show_premises_overview(callback.message, state, uid)
        return
    if status == 429:
        await callback.message.edit_text("Слишком много отправок, попробуйте позже.")
        return

    sd = await state.get_data()
    pending = sd.get("pending_premise", {})
    ptype = pending.get("display", "").split(" ")[0] if pending else ""

    refreshed = await api.get_my_data(uid)
    premises = refreshed.get("premises", [])
    await state.update_data(user_premises=premises, user_data=refreshed)

    if ptype in APARTMENT_TYPES or any(t in ptype for t in ("Квартира", "Офис", "апартамент")):
        lines = ["Ваши помещения:"]
        for p in premises:
            lines.append(f"  ✓ {p['display']}")
        lines.append("")
        lines.append("У вас есть машиноместо или кладовка в этом доме?")
        lines.append("Для добавления пришлите номер, например: мм 12, кладовка 5a")
        await callback.message.edit_text("\n".join(lines), reply_markup=kb.offer_parking_storage_kb())
        await state.set_state(Survey.OFFER_PARKING_STORAGE)
    else:
        lines = ["Ваши помещения:"]
        for p in premises:
            lines.append(f"  ✓ {p['display']}")
        lines.append("")
        lines.append("Хотите добавить ещё помещение?\nВведите номер или нажмите «Продолжить».")
        await callback.message.edit_text("\n".join(lines), reply_markup=kb.offer_more_kb())
        await state.set_state(Survey.OFFER_MORE)


@router.callback_query(F.data == "confirm_no", Survey.CONFIRM_PREMISE)
async def cb_confirm_no(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = callback.from_user.id
    await show_premises_overview(callback.message, state, uid, edit=True)


# --- OFFER_PARKING_STORAGE ---

@router.message(Survey.OFFER_PARKING_STORAGE)
async def offer_parking_text(message: Message, state: FSMContext):
    await premises_text_input(message, state)


# --- OFFER_MORE ---

@router.message(Survey.OFFER_MORE)
async def offer_more_text(message: Message, state: FSMContext):
    await premises_text_input(message, state)


# --- REMOVE_PREMISE ---

@router.callback_query(F.data.startswith("rm:"), Survey.REMOVE_PREMISE)
async def cb_rm_select(callback: CallbackQuery, state: FSMContext):
    premise_id = callback.data.split(":", 1)[1]
    await callback.answer()
    sd = await state.get_data()
    premises = sd.get("user_premises", [])
    chosen = next((p for p in premises if p["premise_id"] == premise_id), None)
    label = chosen["short_display"] if chosen else premise_id
    await state.update_data(remove_premise_id=premise_id, remove_premise_label=label)
    await callback.message.edit_text(
        f"Убрать «{label}» из вашего списка?\nВаши ответы по этому помещению тоже будут удалены.",
        reply_markup=kb.confirm_remove_premise_kb(premise_id),
    )
    await state.set_state(Survey.CONFIRM_REMOVE_PREMISE)


@router.callback_query(F.data == "back_from_remove", Survey.REMOVE_PREMISE)
async def cb_back_from_remove(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = callback.from_user.id
    await show_premises_overview(callback.message, state, uid, edit=True)


# --- CONFIRM_REMOVE_PREMISE ---

@router.callback_query(F.data.startswith("rm_yes:"), Survey.CONFIRM_REMOVE_PREMISE)
async def cb_rm_confirm(callback: CallbackQuery, state: FSMContext):
    premise_id = callback.data.split(":", 1)[1]
    await callback.answer()
    uid = callback.from_user.id
    result = await api.remove_premise(uid, premise_id)
    if result.get("_status") == 404:
        await callback.message.edit_text("Помещение не найдено.")
    else:
        await callback.message.edit_text("Помещение убрано.")
    await show_premises_overview(callback.message, state, uid)


@router.callback_query(F.data == "rm_cancel", Survey.CONFIRM_REMOVE_PREMISE)
async def cb_rm_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    sd = await state.get_data()
    premises = sd.get("user_premises", [])
    await callback.message.edit_text("Какое помещение убрать из списка?", reply_markup=kb.remove_premise_kb(premises))
    await state.set_state(Survey.REMOVE_PREMISE)
