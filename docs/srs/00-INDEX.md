# Спецификация системных требований (SRS): Кворум-МКД — Навигация

**Версия:** 1.0  
**Основа:** BRD v2.2, Архитектура (arch.md), Список фич (feature-list.md)

Документация SRS разбита на модули: сначала **BE-01**, затем **базовый админ и схема БД** (03), **цепочка импорта** (04), далее **форма и контакты** (05), **валидация** (06) и **остальные фичи** (98).

---

## Определения и соглашения

Перед работой с требованиями см. **[01-definitions.md](01-definitions.md)**:
- Атомарность требований (SR-xxx)
- Маркировка (⚠️ риск, 🤔 допущение, 📋 сводка)
- Технические ограничения и формат API (JSON)

---

## Карта зависимостей

**От развёртывания до загрузки реестра.** Ссылки по узлам: [02](02-BE-01-infrastructure.md) · [03](03-basic-admin.md) · [04](04-import-chain.md)

| [BE-01](02-BE-01-infrastructure.md) | [LOST-01](03-basic-admin.md) → [BE-02](03-basic-admin.md) | [ADM-01](03-basic-admin.md) → [ADM-04](03-basic-admin.md) | [CORE-01](04-import-chain.md) → [LOST-02](04-import-chain.md) |
|------------------------------------|----------------------------------------------------------|-----------------------------------------------------------|-----------------------------------------------------------------|
| [02](02-BE-01-infrastructure.md)    | [03](03-basic-admin.md)                                  | [03](03-basic-admin.md)                                   | [04](04-import-chain.md)                                        |

```
BE-01
(инфра: Docker, РФ)
 ↓
LOST-01  ──→  BE-02          ADM-01  ──→  ADM-04
(схема БД)    (шифрование)   (OAuth)      (управление админами)
 ↓     ↘           ↓              ↓
 ↓      └──────────┴────→  CORE-01  ──→  LOST-02
 ↓              (импорт CSV/XLS)    (страница загрузки)
```

CORE-01 невозможен без LOST-01 и BE-02. LOST-02 (UI загрузки) и вызов CORE-01 требуют авторизации админа (ADM-01).

**После LOST-02** (данные помещений в БД — навигация и анкеты). Ссылки по узлам: [04](04-import-chain.md) · [05](05-add-contacts.md) · [06](06-validation.md)

| [LOST-02](04-import-chain.md) | [FE-03](05-add-contacts.md) → [FE-04](05-add-contacts.md) | [CORE-02](06-validation.md) → [VAL-01](06-validation.md) |
|-------------------------------|------------------------------------------------------------|---------------------------------------------------------|
| [04](04-import-chain.md)     | [05](05-add-contacts.md)                                   | [06](06-validation.md)                                  |

```
LOST-02
   ↓
FE-03  ──→  FE-04  ──→  CORE-02  ──→  VAL-01
(фильтры     (форма      (валидация    (админ:
 подъезд→     анкеты,     и лимиты     смена статуса
 номер)       POST        при submit)   контакта)
              /submit)
```

FE-03 и FE-04 опираются на реестр помещений (CORE-01). Отправка формы (FE-04) проходит через CORE-02. VAL-01 и модерация — после появления контактов. Telegram-бот (BOT-01…04) — в [15-bot-telegram.md](15-bot-telegram.md). Карта и прочие фичи из бэклога — в [98-backlog.md](98-backlog.md).

---

## Модули SRS

| № | Модуль | Фичи | Содержание |
|--|--------|------|------------|
| 1 | [BE-01 Инфраструктура](02-BE-01-infrastructure.md) | BE-01 | Развёртывание в РФ, Docker (frontend, backend, db) |
| 2 | [Базовый админ и схема БД](03-basic-admin.md) | LOST-01, BE-02, ADM-01, ADM-04 | Миграции (Alembic), таблицы admins/premises/contacts, шифрование ПДн, Telegram OAuth, управление админами |
| 9 | [Вход по логину/паролю и смена пароля](09-admin-login-password.md) | ADM-01-PWD | Альтернатива Telegram OAuth: логин/пароль, смена пароля, управление логином/паролем суперадмином |
| 3 | [Цепочка импорта](04-import-chain.md) | CORE-01, LOST-02 | Импорт реестра CSV/XLS, страница загрузки (инструкция, валидация колонок) |
| 10 | [Загрузка контактов](10-import-contacts.md) | ADM-06, ADM-07, ADM-08 | Импорт только контактов (ADM-06); интерфейс загрузки контактов (ADM-07); формирование шаблона контактов по подъезду с аудитом (ADM-08) |
| 11 | [Модерация и аудит суперадмина](11-adm02-adm05-moderation-superadmin-audit.md) | ADM-02, ADM-05 | Интерфейс модерации (фильтры IP/TimeRange, пакетный перевод в «Неактуальные»); логирование добавления/удаления админов |
| 12 | [Согласие администратора с Политикой (152-ФЗ)](12-admin-policy-consent.md) | ADM-09 | Обязательное принятие ответственности за ПДн при первом входе; фиксация версии и даты в БД; 403 без согласия; аудит |
| 4 | [Форма и контакты](05-add-contacts.md) | FE-03, FE-04, … | Каскадные фильтры, форма анкеты, добавление контактов |
| 5 | [Валидация](06-validation.md) | VAL-01, CORE-02 | Смена статуса контакта, валидация и лимиты, дедупликация |
| 6 | [Кворум (базовый расчёт)](08-core04-quorum.md) | CORE-04 | API расчёта долей, отображение на главной |
| 7 | [Остальные фичи](98-backlog.md) | FE-01, FE-02, ADM-03, OPS-01…03, CORE-06 | Карта, операции |
| 13 | [EntrancePicker и шахматка](13-home-premises-chessboard.md) | UI-01, FE-06 | Компонент выбора подъезда; таблица этажей на главной, клик → форма/админка |
| 14 | [Cross-object: sessionStorage и Nudge](14-fe05-cross-object-session.md) | FE-05 | sessionStorage для автозаполнения между помещениями, Nudge-модал после анкеты |
| 15 | [Telegram-бот](15-bot-telegram.md) | BOT-01…04 | Поиск помещения, анкета в боте, личный кабинет, синхронизация с вебом |
| — | [Итоговая сводка (Action Items)](99-summary.md) | — | Вопросы к бизнесу, допущения, риски |

---

## Быстрый поиск по коду фичи

| Код | Файл |
|-----|------|
| BE-01 | [02-BE-01-infrastructure.md](02-BE-01-infrastructure.md) |
| BE-03, BE-04, CORE-03 | [07-audit-ratelimit.md](07-audit-ratelimit.md) |
| LOST-01, BE-02, ADM-01, ADM-04 | [03-basic-admin.md](03-basic-admin.md) |
| ADM-01-PWD | [09-admin-login-password.md](09-admin-login-password.md) |
| CORE-01, LOST-02 | [04-import-chain.md](04-import-chain.md) |
| ADM-06, ADM-07, ADM-08 | [10-import-contacts.md](10-import-contacts.md) |
| FE-03, FE-04, … | [05-add-contacts.md](05-add-contacts.md) |
| VAL-01, CORE-02 | [06-validation.md](06-validation.md) |
| CORE-04 | [08-core04-quorum.md](08-core04-quorum.md) |
| ADM-02, ADM-05 | [11-adm02-adm05-moderation-superadmin-audit.md](11-adm02-adm05-moderation-superadmin-audit.md) |
| ADM-09 | [12-admin-policy-consent.md](12-admin-policy-consent.md) |
| FE-05 | [14-fe05-cross-object-session.md](14-fe05-cross-object-session.md) |
| FE-01, FE-02, ADM-03, OPS-01…03, CORE-06 | [98-backlog.md](98-backlog.md) |
| BOT-01…04 | [15-bot-telegram.md](15-bot-telegram.md) |
| UI-01, FE-06 | [13-home-premises-chessboard.md](13-home-premises-chessboard.md) |
| Итоговая сводка | [99-summary.md](99-summary.md) |

---

Полный монолит сохранён в корне: [../srs.md](../srs.md).
