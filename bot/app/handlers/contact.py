"""Handlers: CONTACT_MANAGE, ENTER_PHONE, CONFIRM_DELETE."""
import logging
import re

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.states import Survey
from app import backend_client as api
from app import keyboards as kb

logger = logging.getLogger(__name__)
router = Router()

PHONE_RE = re.compile(r"^\+?[0-9\s\-()]{7,20}$")
POLICY_URL = "https://jksilver.ru/policy"

CONSENT_CONTACTS = (
    "Я даю согласие на обработку моих контактных данных (телефон, мессенджер, e-mail — в случае их заполнения) "
    "администраторам системы для организации и подготовки Общих собраний собственников в ЖК Silver. "
    "С Политикой конфиденциальности ознакомлен(а).\n"
    f"Политика: {POLICY_URL}\n\n"
    "Согласие может быть отозвано в любой момент без ущерба для проведения Общих собраний собственников "
    "(уже поданные голоса и учёт кворума при необходимости сохраняются в обезличенном виде)."
)


async def show_contact_manage(msg: Message, state: FSMContext, edit: bool = False):
    """CONTACT_MANAGE: при наличии телефона — только номер и кнопки (согласие уже дано при добавлении); без телефона — подсказка, согласие на отдельном шаге."""
    sd = await state.get_data()
    user_data = sd.get("user_data", {})
    phone = user_data.get("phone")

    if phone:
        text = (
            f"Ваш телефон для связи: {phone}\n"
            "Проверьте номер. Если нужно — исправьте или удалите."
        )
        markup = kb.contact_manage_has_phone_kb()
    else:
        text = (
            "У нас пока нет вашего телефона для связи.\n"
            "Нажмите «Добавить телефон» или введите номер — перед сохранением потребуется согласие на обработку данных."
        )
        markup = kb.contact_manage_no_phone_kb()

    await state.set_state(Survey.CONTACT_MANAGE)
    if edit:
        await msg.edit_text(text, reply_markup=markup)
    else:
        await msg.answer(text, reply_markup=markup)


async def show_consent_step(msg: Message, state: FSMContext, edit: bool = False):
    """Показать шаг согласия (две кнопки). pending_phone в state — если есть, после «Согласен» сохраняем его."""
    await state.set_state(Survey.CONTACT_CONSENT)
    text = CONSENT_CONTACTS
    markup = kb.consent_agree_decline_kb()
    if edit:
        await msg.edit_text(text, reply_markup=markup)
    else:
        await msg.answer(text, reply_markup=markup)


@router.callback_query(F.data == "contact_ok", Survey.CONTACT_MANAGE)
async def cb_contact_ok(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from app.handlers.survey import show_done
    await show_done(callback.message, state, edit=True)


@router.callback_query(F.data == "enter_phone", Survey.CONTACT_MANAGE)
async def cb_enter_phone(callback: CallbackQuery, state: FSMContext):
    """Добавить телефон: сначала шаг согласия (если телефона ещё нет — уже проверено кнопкой только в ветке без телефона)."""
    await callback.answer()
    sd = await state.get_data()
    if sd.get("user_data", {}).get("phone"):
        await callback.message.delete()
        await callback.message.answer(
            "Введите номер телефона в формате +7XXXXXXXXXX\nили поделитесь контактом.",
            reply_markup=kb.enter_phone_reply_kb(),
        )
        await state.set_state(Survey.ENTER_PHONE)
        return
    await callback.message.edit_text(CONSENT_CONTACTS, reply_markup=kb.consent_agree_decline_kb())
    await state.set_state(Survey.CONTACT_CONSENT)


@router.callback_query(F.data == "consent_agree", Survey.CONTACT_CONSENT)
async def cb_consent_agree(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    sd = await state.get_data()
    pending = sd.get("pending_phone")
    if pending:
        uid = callback.from_user.id
        result = await api.update_answers(uid, phone=pending)
        if result.get("_status") == 429:
            await callback.message.edit_text("Слишком много отправок, попробуйте позже.")
            await state.set_state(Survey.CONTACT_MANAGE)
            await state.update_data(pending_phone=None)
            return
        ud = sd.get("user_data", {})
        ud["phone"] = pending
        await state.update_data(user_data=ud, pending_phone=None)
        await show_contact_manage(callback.message, state, edit=True)
        return
    await callback.message.delete()
    await callback.message.answer(
        "Введите номер телефона в формате +7XXXXXXXXXX\nили поделитесь контактом.",
        reply_markup=kb.enter_phone_reply_kb(),
    )
    await state.set_state(Survey.ENTER_PHONE)


@router.callback_query(F.data == "consent_decline", Survey.CONTACT_CONSENT)
async def cb_consent_decline(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(pending_phone=None)
    await show_contact_manage(callback.message, state, edit=True)


@router.callback_query(F.data == "delete_phone", Survey.CONTACT_MANAGE)
async def cb_delete_phone(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "Удалить ваш телефон из системы?\nОстальные данные (помещения, ответы) сохранятся.",
        reply_markup=kb.confirm_delete_kb(),
    )
    await state.set_state(Survey.CONFIRM_DELETE)


@router.callback_query(F.data == "back", Survey.CONTACT_MANAGE)
async def cb_back_contact(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from app.handlers.survey import show_barrier_vote
    await show_barrier_vote(callback.message, state, edit=True)


@router.message(Survey.CONTACT_MANAGE)
async def contact_text_input(message: Message, state: FSMContext):
    """Ввод телефона на шаге CONTACT_MANAGE: если телефона ещё нет — сначала шаг согласия с сохранённым номером."""
    text = (message.text or "").strip()
    if not text:
        return
    if not PHONE_RE.match(text):
        await message.answer("Неверный формат. Введите номер в формате +7XXXXXXXXXX.")
        return
    sd = await state.get_data()
    user_data = sd.get("user_data", {})
    if user_data.get("phone"):
        uid = message.from_user.id
        result = await api.update_answers(uid, phone=text)
        if result.get("_status") == 429:
            await message.answer("Слишком много отправок, попробуйте позже.")
            return
        user_data["phone"] = text
        await state.update_data(user_data=user_data)
        await show_contact_manage(message, state)
        return
    await state.update_data(pending_phone=text)
    await show_consent_step(message, state)


# --- ENTER_PHONE ---

@router.message(Survey.ENTER_PHONE, F.contact)
async def enter_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    uid = message.from_user.id
    result = await api.update_answers(uid, phone=phone)
    sd = await state.get_data()
    ud = sd.get("user_data", {})
    ud["phone"] = phone
    await state.update_data(user_data=ud)
    await message.answer("Телефон сохранён.", reply_markup=ReplyKeyboardRemove())
    await show_contact_manage(message, state)


@router.message(Survey.ENTER_PHONE)
async def enter_phone_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.startswith("/"):
        if text == "/back":
            await message.answer("Возврат.", reply_markup=ReplyKeyboardRemove())
            await show_contact_manage(message, state)
            return
        if text == "/cancel":
            await state.clear()
            await message.answer("Диалог отменён.", reply_markup=ReplyKeyboardRemove())
            from app.handlers.start import get_welcome_text
            from app import backend_client as api
            welcome_text = await get_welcome_text()
            role_data = await api.get_my_role(message.from_user.id)
            show_broadcast = role_data.get("role") == "super_administrator"
            await message.answer(welcome_text, reply_markup=kb.idle_kb(show_broadcast=show_broadcast))
            return
    if not PHONE_RE.match(text):
        await message.answer("Неверный формат. Введите номер в формате +7XXXXXXXXXX.")
        return
    uid = message.from_user.id
    result = await api.update_answers(uid, phone=text)
    if result.get("_status") == 429:
        await message.answer("Слишком много отправок, попробуйте позже.")
        return
    sd = await state.get_data()
    ud = sd.get("user_data", {})
    ud["phone"] = text
    await state.update_data(user_data=ud)
    await message.answer("Телефон сохранён.", reply_markup=ReplyKeyboardRemove())
    await show_contact_manage(message, state)


# --- CONFIRM_DELETE ---

@router.callback_query(F.data == "del_yes", Survey.CONFIRM_DELETE)
async def cb_del_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = callback.from_user.id
    await api.update_answers(uid, phone="")
    sd = await state.get_data()
    ud = sd.get("user_data", {})
    ud["phone"] = None
    await state.update_data(user_data=ud)
    await callback.message.edit_text("Телефон удалён.")
    await show_contact_manage(callback.message, state)


@router.callback_query(F.data == "del_cancel", Survey.CONFIRM_DELETE)
async def cb_del_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_contact_manage(callback.message, state, edit=True)
