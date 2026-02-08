# FE-03, FE-04, ADM-03 — Выбор помещения, форма анкеты, добавление контакта админом

Краткое описание API и интерфейсов по [05-add-contacts.md](../srs/05-add-contacts.md).

---

## 1. FE-03 — Каскадные фильтры помещений

**Маршруты (без авторизации):**

- `GET /api/premises/entrances` — список подъездов.
- `GET /api/premises/floors?entrance=<значение>` — этажи по подъезду.
- `GET /api/premises/types?entrance=&floor=` — типы помещений.
- `GET /api/premises/numbers?entrance=&floor=&type=` — номера помещений и `premise_id` (кадастровый номер).
- `GET /api/premises/normalize?number=<строка>` — нормализация номера помещения (как при импорте CORE-01).

Ответ по номерам: `{ "premises": [ { "number": "45", "premise_id": "77:01:0001001:123" } ] }`.  
Фронт: страница **/premises** с каскадными выпадающими списками; после выбора номера — переход к форме **/form**.

---

## 2. FE-04 — Форма анкеты (POST /api/submit)

**Метод:** `POST /api/submit`  
**Тело (JSON):**  
`premise_id`, `is_owner`, `phone`, `email`, `telegram_id` (хотя бы одно из трёх), `vote_for`, `vote_format` (paper | electronic), `registered_ed`, `consent_version`, `captcha_token` (от Turnstile).

**Ответы:**

- Успех: `{ "success": true, "message": "Данные приняты" }`.
- 400: ошибки валидации или лимит 10 невалидированных на помещение.
- 409: конфликт данных (существующий контакт с другими значениями).
- 429: превышен лимит отправок с IP (заголовок `Retry-After`).

**Капча:** при заданном `TURNSTILE_SECRET_KEY` на бэкенде проверяется токен Turnstile. На фронте задаётся `VITE_TURNSTILE_SITE_KEY`; при отсутствии ключа виджет не показывается (режим разработки).

**Лимиты:** до 10 невалидированных контактов на помещение (CORE-02); по умолчанию до 10 отправок с одного IP в час (конфиг `SUBMIT_RATE_LIMIT_PER_HOUR`).

Фронт: страница **/form** (переход с /premises с выбранным помещением). Обязательны: «Я собственник», хотя бы один контакт, согласие на ОПД, при наличии ключа — прохождение капчи.

---

## 3. ADM-03 — Добавление контакта админом

**Метод:** `POST /api/admin/contacts`  
**Авторизация:** `Authorization: Bearer <JWT>` (роль administrator или super_administrator).

**Тело (JSON):**  
`premise_id`, `phone`, `email`, `telegram_id` (хотя бы одно), `vote_for`, `vote_format`, `registered_ed`.

**Ответ:** 201, `{ "contact_id": <id>, "status": "validated" }`.  
Капча не требуется; применяются те же валидации форматов и шифрование (BE-02). Статус контакта устанавливается «валидирован».

---

## 4. Переменные окружения (бэкенд)

- `TURNSTILE_SECRET_KEY` — секрет Turnstile (опционально; при отсутствии капча не проверяется).
- `SUBMIT_RATE_LIMIT_PER_HOUR` — лимит отправок с IP в час (по умолчанию 10).

Фронт (Vite):

- `VITE_TURNSTILE_SITE_KEY` — сайт-ключ Turnstile (опционально).
- `VITE_POLICY_URL` — ссылка на политику конфиденциальности (по умолчанию /policy).
