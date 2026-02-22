"""Рассылка суперадмином всем пользователям; отправка сообщения админам — любым пользователем."""
import asyncio
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


@router.callback_query(F.data == "broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    """Рассылка: только суперадмин. Переход в состояние ввода текста."""
    await callback.answer()
    role_data = await api.get_my_role(callback.from_user.id)
    if role_data.get("role") != "super_administrator":
        await callback.message.answer("Доступ запрещён. Функция доступна только суперадминистратору.")
        return
    await state.set_state(Survey.BROADCAST_WAIT_TEXT)
    await callback.message.edit_text(
        "Введите текст рассылки. Он будет отправлен всем пользователям, которые хотя бы раз запускали бота.\n\n"
        "Для отмены нажмите /cancel."
    )


@router.message(Survey.BROADCAST_WAIT_TEXT, Command("cancel"))
@router.message(Survey.TO_ADMINS_WAIT_TEXT, Command("cancel"))
async def notifications_cancel(message: Message, state: FSMContext):
    await state.clear()
    role_data = await api.get_my_role(message.from_user.id)
    show_broadcast = role_data.get("role") == "super_administrator"
    await message.answer("Отменено.", reply_markup=kb.idle_kb(show_broadcast=show_broadcast))


@router.message(Survey.BROADCAST_WAIT_TEXT, F.text)
async def broadcast_send(message: Message, state: FSMContext):
    """Отправить рассылку всем из broadcast_recipients."""
    if not hasattr(state.storage, "get_all_broadcast_chat_ids"):
        await state.clear()
        await message.answer("Ошибка: хранилище рассылки недоступно.", reply_markup=kb.idle_kb())
        return
    role_data = await api.get_my_role(message.from_user.id)
    if role_data.get("role") != "super_administrator":
        await state.clear()
        await message.answer("Доступ запрещён.", reply_markup=kb.idle_kb())
        return
    chat_ids = await state.storage.get_all_broadcast_chat_ids()
    text = message.text or "(пусто)"
    sent = 0
    failed = 0
    for cid in chat_ids:
        try:
            await message.bot.send_message(cid, text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning("broadcast to %s failed: %s", cid, e)
            failed += 1
    await state.clear()
    role_data = await api.get_my_role(message.from_user.id)
    show_broadcast = role_data.get("role") == "super_administrator"
    await message.answer(
        f"Рассылка завершена. Отправлено: {sent}, ошибок: {failed}.",
        reply_markup=kb.idle_kb(show_broadcast=show_broadcast),
    )


@router.callback_query(F.data == "to_admins")
async def cb_to_admins(callback: CallbackQuery, state: FSMContext):
    """Написать админам: доступно всем. Переход в состояние ввода текста."""
    await callback.answer()
    await state.set_state(Survey.TO_ADMINS_WAIT_TEXT)
    await callback.message.edit_text(
        "Введите сообщение для администраторов. Оно будет доставлено всем админам системы.\n\n"
        "Для отмены нажмите /cancel."
    )


@router.message(Survey.TO_ADMINS_WAIT_TEXT, F.text)
async def to_admins_send(message: Message, state: FSMContext):
    """Отправить сообщение пользователя всем админам."""
    admin_ids = await api.get_admins_telegram_ids()
    if not admin_ids:
        await state.clear()
        role_data = await api.get_my_role(message.from_user.id)
        show_broadcast = role_data.get("role") == "super_administrator"
        await message.answer(
            "Список администраторов пуст. Сообщение никому не отправлено.",
            reply_markup=kb.idle_kb(show_broadcast=show_broadcast),
        )
        return
    user_label = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
    text = message.text or "(пусто)"
    admin_message = f"Сообщение от пользователя {user_label} (id={message.from_user.id}):\n\n{text}"
    sent = 0
    for tid in admin_ids:
        try:
            await message.bot.send_message(int(tid), admin_message)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning("to_admins to %s failed: %s", tid, e)
    await state.clear()
    role_data = await api.get_my_role(message.from_user.id)
    show_broadcast = role_data.get("role") == "super_administrator"
    await message.answer(
        f"Сообщение доставлено администраторам ({sent} из {len(admin_ids)}).",
        reply_markup=kb.idle_kb(show_broadcast=show_broadcast),
    )


@router.message(Survey.BROADCAST_WAIT_TEXT)
@router.message(Survey.TO_ADMINS_WAIT_TEXT)
async def notifications_wait_text_else(message: Message, state: FSMContext):
    """Не текст в состоянии ввода: подсказка."""
    await message.answer("Отправьте текстовое сообщение или /cancel для отмены.")
