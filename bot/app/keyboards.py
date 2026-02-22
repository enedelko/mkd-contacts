"""Keyboard builders for bot states."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def idle_kb(show_broadcast: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Я собственник", callback_data="owner")],
        [InlineKeyboardButton(text="Мои данные", callback_data="mydata")],
        [InlineKeyboardButton(text="Написать админам", callback_data="to_admins")],
        [InlineKeyboardButton(text="Помощь", callback_data="help")],
    ]
    if show_broadcast:
        rows.insert(-1, [InlineKeyboardButton(text="Рассылка", callback_data="broadcast")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premises_overview_new_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def premises_overview_existing_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить помещение", callback_data="add_premise")],
        [InlineKeyboardButton(text="Убрать помещение", callback_data="remove_premise")],
        [InlineKeyboardButton(text="Перейти к вопросам \u27a1", callback_data="to_questions")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def disambiguate_kb(matches: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=m["short_display"], callback_data=f"pick:{m['premise_id']}")]
        for m in matches[:5]
    ]
    rows.append([InlineKeyboardButton(text="Ввести заново", callback_data="retry_premise")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_premise_kb(premise_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data=f"confirm_yes:{premise_id}")],
        [InlineKeyboardButton(text="Нет, ввести другое", callback_data="confirm_no")],
    ])


def offer_parking_storage_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ММ/кладовку", callback_data="add_parking_input")],
        [InlineKeyboardButton(text="Нет, продолжить \u27a1", callback_data="to_questions")],
        [InlineKeyboardButton(text="Убрать помещение", callback_data="remove_premise")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def enter_premise_only_kb() -> InlineKeyboardMarkup:
    """Клавиатура «только ввод»: одна кнопка Отмена."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def offer_more_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить помещение", callback_data="add_more_input")],
        [InlineKeyboardButton(text="Продолжить \u27a1", callback_data="to_questions")],
        [InlineKeyboardButton(text="Убрать помещение", callback_data="remove_premise")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def remove_premise_kb(premises: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=p["short_display"], callback_data=f"rm:{p['premise_id']}")]
        for p in premises
    ]
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="back_from_remove")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_remove_premise_kb(premise_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, убрать", callback_data=f"rm_yes:{premise_id}")],
        [InlineKeyboardButton(text="Отмена", callback_data="rm_cancel")],
    ])


def vote_method_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Планирую установить ЭД", callback_data="vote:ed_plan")],
        [InlineKeyboardButton(text="ЭД установлено, собственность видна", callback_data="vote:ed_ok")],
        [InlineKeyboardButton(text="На бумажном бюллетене", callback_data="vote:paper")],
        [InlineKeyboardButton(text="Не буду голосовать", callback_data="vote:abstain")],
        [InlineKeyboardButton(text="Назад", callback_data="back"),
         InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def barrier_vote_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="За", callback_data="barrier:for")],
        [InlineKeyboardButton(text="Против", callback_data="barrier:against")],
        [InlineKeyboardButton(text="Не определился", callback_data="barrier:undecided")],
        [InlineKeyboardButton(text="Назад", callback_data="back"),
         InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def contact_manage_has_phone_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Всё верно, сохранить \u2713", callback_data="contact_ok")],
        [InlineKeyboardButton(text="Исправить телефон", callback_data="enter_phone")],
        [InlineKeyboardButton(text="Удалить телефон", callback_data="delete_phone")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])


def contact_manage_no_phone_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить телефон", callback_data="enter_phone")],
        [InlineKeyboardButton(text="Пропустить", callback_data="contact_ok")],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ])


def enter_phone_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="\U0001f4f1 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm_delete_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить телефон", callback_data="del_yes")],
        [InlineKeyboardButton(text="Отмена", callback_data="del_cancel")],
    ])


def my_data_view_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить данные", callback_data="edit_data")],
        [InlineKeyboardButton(text="Удалить все мои данные", callback_data="forget")],
        [InlineKeyboardButton(text="Закрыть", callback_data="close")],
    ])


def my_data_empty_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Заполнить анкету", callback_data="owner")],
        [InlineKeyboardButton(text="Закрыть", callback_data="close")],
    ])


def confirm_forget_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить всё", callback_data="forget_yes")],
        [InlineKeyboardButton(text="Отмена", callback_data="forget_cancel")],
    ])


def done_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить данные", callback_data="edit_data")],
        [InlineKeyboardButton(text="Закрыть", callback_data="close")],
    ])
