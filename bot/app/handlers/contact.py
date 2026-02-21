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


async def show_contact_manage(msg: Message, state: FSMContext, edit: bool = False):
    sd = await state.get_data()
    user_data = sd.get("user_data", {})
    phone = user_data.get("phone")

    if phone:
        text = (
            f"Ваш телефон для связи: {phone}\n"
            "Проверьте номер. Если нужно — исправьте или удалите.\n\n"
            f"Отправляя данные, вы соглашаетесь с Политикой конфиденциальности:\n{POLICY_URL}"
        )
        markup = kb.contact_manage_has_phone_kb()
    else:
        text = (
            "У нас пока нет вашего телефона для связи.\n"
            "Поделитесь контактом или введите номер вручную.\n\n"
            f"Отправляя данные, вы соглашаетесь с Политикой конфиденциальности:\n{POLICY_URL}"
        )
        markup = kb.contact_manage_no_phone_kb()

    await state.set_state(Survey.CONTACT_MANAGE)
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
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        "Введите номер телефона в формате +7XXXXXXXXXX\nили поделитесь контактом.",
        reply_markup=kb.enter_phone_reply_kb(),
    )
    await state.set_state(Survey.ENTER_PHONE)


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
    text = (message.text or "").strip()
    if not text:
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
    await show_contact_manage(message, state)


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
            welcome_text = await get_welcome_text()
            await message.answer(welcome_text, reply_markup=kb.idle_kb())
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
