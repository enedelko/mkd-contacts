# ADM-09 — Согласие администратора с Политикой конфиденциальности (152-ФЗ)

Модуль SRS: обязательное принятие администратором и суперадминистратором ответственности за сохранность ПДн при первом входе. Зависимости: ADM-01, ADM-04, BE-03, страница Политики конфиденциальности (frontend: `/policy`, Policy.jsx).

---

### 1. Архитектурный анализ (CoT)
Реализуется на Backend (таблица admins: policy_consent_at, policy_consent_version; API проверки и принятия согласия; зависимость проверки согласия для всех админ/суперадмин-эндпоинтов) и Frontend (страница согласия `/admin/consent`, редирект после входа при отсутствии согласия, обработка 403 с редиректом на страницу согласия). Цель — соответствие 152-ФЗ и БТ: фиксация ответственности лиц, имеющих доступ к ПДн.

### 2. Описание и цель
При первом входе в систему администратор и суперадминистратор обязаны принять ответственность за сохранность и законность обработки персональных данных в соответствии с Политикой конфиденциальности приложения (содержимое — см. разделы 1–10 на странице `/policy`). Версия политики и дата/время согласия фиксируются в БД; факт принятия записывается в аудит-лог. До принятия согласия доступ к любым админ- и суперадмин-эндпоинтам (кроме эндпоинтов проверки и принятия согласия) запрещён (403).

### 3. Функциональные требования
* **SR-ADM09-001:** Система должна хранить в таблице admins признак и дату принятия согласия с Политикой конфиденциальности: колонки policy_consent_at (TIMESTAMP WITH TIME ZONE, nullable) и policy_consent_version (VARCHAR(32), nullable). NULL policy_consent_at означает, что согласие не дано.
* **SR-ADM09-002:** Система должна предоставлять авторизованному администратору эндпоинт GET /api/auth/consent-status, возвращающий признак принятия согласия и версию политики (policy_consent_accepted: bool, policy_consent_version: str | null). Эндпоинт защищён require_admin; проверка наличия согласия для вызова этого эндпоинта не требуется.
* **SR-ADM09-003:** Система должна предоставлять эндпоинт POST /api/auth/consent с телом { consent_version: "1.0" } (версия соответствует Политике на странице /policy). По успешному вызову система обновляет в admins для текущего пользователя policy_consent_at = now(), policy_consent_version = переданная версия. Эндпоинт защищён require_admin без проверки согласия.
* **SR-ADM09-004:** При каждом успешном принятии согласия (POST /api/auth/consent) система должна записывать в audit_log запись: entity_type = "admin", entity_id = telegram_id пользователя, action = "policy_consent", new_value = версия политики, user_id, ip, timestamp. Пароли и токены в лог не попадают.
* **SR-ADM09-005:** Все эндпоинты, защищённые ролью администратора или суперадминистратора (все /api/admin/* и /api/superadmin/*, за исключением /api/auth/consent-status и /api/auth/consent и /api/auth/change-password), должны дополнительно проверять: если у пользователя policy_consent_at IS NULL, возвращать HTTP 403 с единообразным сообщением (например detail = "Policy consent required"), чтобы клиент мог распознать необходимость редиректа на страницу согласия.
* **SR-ADM09-006:** Клиент после успешного входа (логин/пароль или Telegram OAuth) должен запросить GET /api/auth/consent-status; при policy_consent_accepted === false перенаправлять пользователя на страницу /admin/consent, иначе — на главную.
* **SR-ADM09-007:** Клиент должен предоставлять страницу /admin/consent: краткий текст об ответственности за ПДн, ссылку на полную Политику (/policy), обязательный чекбокс принятия ответственности и кнопку «Принять и продолжить». Отправка — POST /api/auth/consent с consent_version "1.0"; при успехе — редирект на главную. Страница доступна только при наличии валидного JWT; при отсутствии токена — редирект на /login.
* **SR-ADM09-008:** При получении от любого запроса к /api/admin/* или /api/superadmin/* ответа 403 с признаком «Policy consent required» (например detail === "Policy consent required") клиент должен перенаправлять пользователя на /admin/consent (replace), чтобы обход согласия по прямой ссылке был невозможен.

### 4. Сценарий использования
**Триггер:** Администратор или суперадминистратор впервые входит в систему (Telegram OAuth или логин/пароль).
**Main Success Scenario:**
1. Пользователь успешно авторизуется; клиент сохраняет JWT и запрашивает GET /api/auth/consent-status.
2. Сервер возвращает policy_consent_accepted: false; клиент перенаправляет на /admin/consent.
3. Пользователь читает текст, отмечает чекбокс и нажимает «Принять и продолжить».
4. Клиент отправляет POST /api/auth/consent с consent_version "1.0"; сервер обновляет admins и пишет запись в audit_log.
5. Клиент перенаправляет на главную; при последующих запросах к админ-API сервер проверяет policy_consent_at и разрешает доступ.
**Alternative Flows:**
* **AF-1 (Прямой переход по ссылке на админ-раздел без согласия):** Запрос к /api/admin/* или /api/superadmin/* возвращает 403 "Policy consent required"; клиент перенаправляет на /admin/consent.
* **AF-2 (Повторный вход):** GET /api/auth/consent-status возвращает policy_consent_accepted: true; клиент перенаправляет на главную без показа страницы согласия.

### 5. Модель данных
**Затрагиваемые сущности:** Таблица admins (LOST-01, 03-basic-admin). Добавляются колонки: policy_consent_at (TIMESTAMP WITH TIME ZONE, nullable), policy_consent_version (VARCHAR(32), nullable). Миграция Alembic (например 007_admins_policy_consent). Таблица audit_log (BE-03): новая разновидность действия action = "policy_consent", new_value = версия политики.

### 6. Интеграции и API
* **GET /api/auth/consent-status** (Authorization: Bearer …). Response: `{ "policy_consent_accepted": bool, "policy_consent_version": str | null }`.
* **POST /api/auth/consent** (Authorization: Bearer …, Body: `{ "consent_version": "1.0" }`). Response: 204 No Content или 200 { "ok": true }. Побочный эффект: UPDATE admins, INSERT audit_log.
* Защита остальных админ-эндпоинтов: зависимость require_admin_with_consent / require_super_admin_with_consent (проверка JWT + запрос policy_consent_at из БД; при NULL — 403, detail = "Policy consent required").

### 7. Нефункциональные требования
* **Security:** Невозможность доступа к админ-функциям без принятия согласия (проверка на бэкенде); версия политики фиксируется для последующего учёта смены редакции.
* **Compliance:** Соответствие БТ и 152-ФЗ в части ответственности операторов и фиксации согласия лиц, имеющих доступ к ПДн.
* **Traceability:** Связь с Политикой конфиденциальности (frontend/src/pages/Policy.jsx); текст страницы согласия должен отсылать к полной Политике по адресу /policy.

### 8. Реализация (Implementation)

| Компонент | Расположение |
|-----------|--------------|
| Миграция policy_consent_at, policy_consent_version | backend/alembic/versions/007_* |
| API consent-status, POST consent, аудит | backend/app/routers/auth.py |
| Зависимости require_*_with_consent | backend/app/jwt_utils.py |
| Замена зависимостей в роутерах | backend/app/routers/admin_contacts.py, audit.py, import_register.py, superadmin.py |
| Страница согласия | frontend/src/pages/AdminConsent.jsx |
| Редирект после входа, обработка 403 | frontend: AuthCallback.jsx, Login.jsx, утилита/обёртка для админ-запросов |
| Маршрут /admin/consent | frontend/src/App.jsx |
