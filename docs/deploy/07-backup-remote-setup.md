# 07 — Настройка удалённого бэкапа (OPS-01)

Настройка на **ПРОМ-сервере**: отдельный пользователь для бэкапа, который может только запустить дамп и отдать stdout, **без доступа** к каталогу проекта и к `.env`.

---

## Зачем

- Localhost (ваша машина) дважды в сутки по SSH получает дамп БД и сохраняет две копии.
- Пользователь, под которым localhost подключается (REMOTE_USER), не должен иметь прав читать `.env` и другие секреты в рабочей папке проекта.
- Решение: отдельный системный пользователь (например `mkd-backup`) + обёртка, которая выполняется от имени владельца приложения (sudo). Обёртка читает только минимальный конфиг (путь, POSTGRES_USER, POSTGRES_DB) и запускает `docker compose exec ... pg_dump`.

---

## 1. На ПРОМ-сервере: пользователь и обёртка

Выполнять от root или через sudo.

### 1.1 Создать пользователя для бэкапа

```bash
adduser --disabled-password --gecos "" mkd-backup
```

Пользователь `mkd-backup` не должен входить в группу владельца каталога приложения и не должен иметь прав на чтение каталога проекта или `.env`. Каталог приложения (например `/home/enedelko/mkd-contacts`) и файл `.env` остаются с правами владельца (например `chmod 700` на каталог или `750` только для владельца и группы, куда `mkd-backup` не входит; `.env` — `chmod 600`).

### 1.2 Установить обёртку и конфиг

Скрипт обёртки лежит в репозитории: `scripts/remote/mkd-backup-dump`. Пример конфига: `scripts/remote/mkd-backup.conf.example`.

```bash
# Скопировать обёртку (из клонированного репо или вручную)
cp /path/to/mkd-contacts/scripts/remote/mkd-backup-dump /usr/local/bin/
chmod 755 /usr/local/bin/mkd-backup-dump

# Владелец — root или владелец приложения (например enedelko)
chown root:root /usr/local/bin/mkd-backup-dump
```

Конфиг (без секретов — только путь к приложению и имена пользователя/БД):

```bash
cp /path/to/mkd-contacts/scripts/remote/mkd-backup.conf.example /etc/mkd-backup.conf
chmod 644 /etc/mkd-backup.conf
nano /etc/mkd-backup.conf   # задать MKDBACKUP_APP_PATH (путь к каталогу приложения)
```

Пример содержимого `/etc/mkd-backup.conf`:

```bash
MKDBACKUP_APP_PATH=/home/enedelko/mkd-contacts
POSTGRES_USER=mkd
POSTGRES_DB=mkd_contacts
```

Обёртка при запуске читает этот конфиг и выполняет `cd $MKDBACKUP_APP_PATH && docker compose exec -T db pg_dump ...`. Пароль к БД берётся из `.env` в каталоге приложения — его читает уже процесс, запущенный от владельца приложения (через sudo), а не от `mkd-backup`.

### 1.3 Sudo: разрешить mkd-backup запускать только обёртку

Создайте файл `/etc/sudoers.d/mkd-backup` (подставьте своё имя пользователя — владельца приложения вместо `enedelko`):

```bash
# mkd-backup может без пароля запускать только обёртку от имени владельца приложения
mkd-backup ALL=(enedelko) NOPASSWD: /usr/local/bin/mkd-backup-dump
```

Проверка прав:

```bash
chmod 440 /etc/sudoers.d/mkd-backup
visudo -c
```

### 1.4 SSH: одна разрешённая команда для ключа бэкапа

В домашней директории пользователя `mkd-backup` создайте `~/.ssh` и `authorized_keys`. Ключ, с которого заходит localhost для бэкапа, должен иметь принудительную команду — без shell и без произвольных команд.

На ПРОМ-сервере (подставьте `enedelko` и путь к обёртке при необходимости):

```bash
sudo -u mkd-backup mkdir -p /home/mkd-backup/.ssh
sudo -u mkd-backup chmod 700 /home/mkd-backup/.ssh
```

В `/home/mkd-backup/.ssh/authorized_keys` одна строка на ключ (пример; в одну строку):

```
command="sudo -u enedelko /usr/local/bin/mkd-backup-dump",no-port-forwarding,no-X11-forwarding,no-agent-forwarding ssh-ed25519 AAAA... ваш_публичный_ключ
```

То есть при входе под `mkd-backup` с этого ключа всегда выполняется только `sudo -u enedelko /usr/local/bin/mkd-backup-dump`; вывод (дамп) уходит в stdout. Интерактивного shell нет.

```bash
sudo -u mkd-backup chmod 600 /home/mkd-backup/.ssh/authorized_keys
```

### 1.5 Проверка с ПРОМ-сервера

От пользователя с правами на каталог приложения (или root):

```bash
sudo -u mkd-backup sudo -u enedelko /usr/local/bin/mkd-backup-dump | head -20
```

Должны появиться первые строки SQL-дампа. Если ошибка «permission denied» на каталог или docker — проверьте, что обёртка запускается от `enedelko` (или от того пользователя, которому принадлежит каталог и который в группе docker).

---

## 2. На localhost: конфиг и запуск

Скрипт и конфиг лежат **вне репозитория**: `~/mkd-contacts-backup/`.

- `daily-backup.sh` — основной скрипт (уже создан при реализации OPS-01).
- `daily-backup.env` — заполните `REMOTE_HOST` и `REMOTE_USER=mkd-backup`, оставьте `REMOTE_USE_WRAPPER=true`.

Пример `~/.mkd-contacts-backup/daily-backup.env`:

```bash
REMOTE_HOST=your-prom-host.example.com
REMOTE_USER=mkd-backup
REMOTE_USE_WRAPPER=true
```

Запуск вручную:

```bash
. ~/mkd-contacts-backup/daily-backup.env
~/mkd-contacts-backup/daily-backup.sh
```

Cron (дважды в сутки по Москве):

```cron
0 1,13 * * * TZ=Europe/Moscow . /home/enedelko/mkd-contacts-backup/daily-backup.env; /home/enedelko/mkd-contacts-backup/daily-backup.sh
```

Бэкапы появятся в `/mnt/seagate6tb/backup/mkd-contacts/` и `/mnt/storage/backup/mkd-contacts/` (по 28 последних в каждом каталоге).

---

## 3. Итог

- **REMOTE_USER** = `mkd-backup` на ПРОМ не имеет прав читать каталог проекта или `.env`.
- Он только запускает одну команду (обёртку), которая выполняется от владельца приложения и делает `pg_dump`.
- Localhost получает только поток дампа по SSH и не имеет доступа к секретам на remote.
