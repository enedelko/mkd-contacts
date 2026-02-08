# VAL-01, CORE-02 — Валидация и смена статуса контакта

Краткое описание по [06-validation.md](../srs/06-validation.md).

---

## 1. VAL-01 — Смена статуса контакта

**Метод:** `PATCH /api/admin/contacts/{contact_id}/status`  
**Авторизация:** `Authorization: Bearer <JWT>` (роль administrator или super_administrator).

**Тело (JSON):**
```json
{
  "status": "validated"
}
```
или `"status": "inactive"`.

**Ответ (успех):** `{ "contact_id": <id>, "status": "validated" }` (или inactive).

**Ошибки:** 404 (контакт не найден), 403 (нет прав), 400 (неверный статус).

После смены статуса в таблицу `audit_log` записывается факт изменения (entity_type=contact, action=status_change, old_value, new_value, user_id, ip, created_at). Миграция `002_audit_log` создаёт таблицу при `alembic upgrade head`.

---

## 2. CORE-02 — Валидация и лимиты при приёме анкеты

Реализовано в рамках **POST /api/submit** ([05-add-contacts](../deploy/05-add-contacts.md)):

- **Форматы полей:** проверка телефона, email, telegram_id в [backend/app/validators.py](../../backend/app/validators.py).
- **Лимит 10 невалидированных на помещение:** проверка в [submit_service.py](../../backend/app/submit_service.py); при превышении — 400 с сообщением «Premise limit exceeded».
- **Дедупликация по Blind Index:** поиск существующего контакта по помещению и phone_idx/email_idx/telegram_id_idx; полное совпадение → обновление даты; частичное при пустых полях → дополнение; конфликт → 409 CONTACT_CONFLICT.

Отдельного API для CORE-02 не требуется — правила применяются при каждой отправке анкеты.
