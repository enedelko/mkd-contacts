# Certbot (Let's Encrypt) для вашего домена

Скопируйте этот файл в `06-certbot.md` и подставьте свой домен, путь к проекту и email.  
Файл `06-certbot.md` добавлен в `.gitignore` и не попадёт в репозиторий.

Чтобы работали **https://YOUR_DOMAIN/** и **Telegram webhook**, нужен доверенный сертификат.

## Предварительные условия

- На роутере проброшены порты **80** и **443** на хост с Nginx.
- Домен указывает на ваш внешний IP (KeenDNS, DDNS или A-запись).

## 1. Установка Certbot

```bash
sudo apt update
sudo apt install certbot
```

## 2. Конфиг Nginx с портом 80 для ACME

В конфиге `/etc/nginx/sites-available/mkd-contacts` должен быть сервер на порту **80** для вашего домена с `location /.well-known/acme-challenge/`. Пример конфига — в репозитории (шаблон без локальных данных: `docs/deploy/nginx-host.example.conf`; свой рабочий конфиг храните локально и не коммитьте).

Скопируйте свой локальный конфиг в систему:

```bash
sudo cp /path/to/your/nginx-mkd-contacts.conf /etc/nginx/sites-available/mkd-contacts
```

Создайте каталог и перезагрузите Nginx:

```bash
sudo mkdir -p /var/lib/letsencrypt
sudo nginx -t && sudo systemctl reload nginx
```

## 3. Первый выпуск сертификата

Убедитесь, что порт 80 доступен с интернета. Запустите:

```bash
sudo certbot certonly --webroot -w /var/lib/letsencrypt -d YOUR_DOMAIN --agree-tos --email YOUR_EMAIL
```

Сертификаты появятся в:

- `/etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem`
- `/etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem`

## 4. Переход Nginx на Let's Encrypt

В блоке HTTPS замените пути на сертификаты Let's Encrypt и перезагрузите Nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 5. Продление сертификата

```bash
sudo certbot renew
```

Опционально: хук для перезагрузки Nginx после продления — см. документацию Certbot.

## 6. WEBHOOK_HOST для бота

В `.env` задайте (порт 443 — по умолчанию для HTTPS):

```bash
WEBHOOK_HOST=https://YOUR_DOMAIN
```

Перезапустите бота:

```bash
cd /path/to/mkd-contacts && docker compose up -d bot
```
