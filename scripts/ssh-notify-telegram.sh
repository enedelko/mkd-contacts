#!/usr/bin/env bash
# Отправка в Telegram оповещения при входе пользователя (SSH или интерактивный).
# Не блокирует вход: вызывать в фоне из .bashrc, например:
#   [ -f /path/to/mkd-contacts/scripts/ssh-notify-telegram.sh ] && ( /path/to/mkd-contacts/scripts/ssh-notify-telegram.sh & )
#
# Параметры в .env (в корне репозитория или APP_DIR):
#   TELEGRAM_BOT_TOKEN  — токен бота (как для остальных уведомлений)
#   SSH_NOTIFY_CHAT_ID  — ID чата для оповещений о входе (или TELEGRAM_CHAT_ID)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${APP_DIR:-$REPO_ROOT}/.env"

# Загрузка переменных из .env (только нужные, без выполнения кода)
if [[ -f "$ENV_FILE" ]]; then
  while IFS= read -r line; do
    [[ "$line" =~ ^#.*$ ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    if [[ "$line" =~ ^(TELEGRAM_BOT_TOKEN|SSH_NOTIFY_CHAT_ID|TELEGRAM_CHAT_ID)= ]]; then
      export "$line"
    fi
  done < "$ENV_FILE"
fi

CHAT_ID="${SSH_NOTIFY_CHAT_ID:-$TELEGRAM_CHAT_ID}"
[[ -z "$TELEGRAM_BOT_TOKEN" || -z "$CHAT_ID" ]] && exit 0

# Текст: HH:MM:SS: вход user@host по SSH / интерактивно / по qemu
TIME=$(date +%H:%M:%S 2>/dev/null || date +%T 2>/dev/null || echo "??:??:??")
USER_NAME="${USER:-unknown}"
HOSTNAME=$(hostname -s 2>/dev/null || echo "unknown")
if [[ -n "${SSH_CLIENT:-}" ]]; then
  VIA="по SSH"
elif [[ -f /sys/class/dmi/id/sys_vendor ]] && grep -qi qemu /sys/class/dmi/id/sys_vendor 2>/dev/null; then
  VIA="по qemu"
else
  VIA="интерактивно"
fi
MSG="${TIME}: вход ${USER_NAME}@${HOSTNAME} ${VIA}"

# Отправка в фоне с таймаутом, чтобы не держать процесс
(
  msg_enc=$(printf '%s' "$MSG" | sed "s/ /%20/g; s/:/%3A/g; s/@/%40/g; s/,/%2C/g; s/\//%2F/g; s/?/%3F/g; s/&/%26/g")
  url="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage?chat_id=${CHAT_ID}&text=${msg_enc}"
  curl -s -o /dev/null --connect-timeout 3 --max-time 5 "$url" 2>/dev/null || true
) &
exit 0
