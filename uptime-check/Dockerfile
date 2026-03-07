# OPS-03: лёгкий контейнер для периодической проверки GET /health и алертов в Telegram
FROM alpine:3.19

RUN apk add --no-cache curl bash

WORKDIR /app
COPY scripts/uptime-check.sh /app/uptime-check.sh
RUN chmod +x /app/uptime-check.sh

# Интервал проверки в секундах (по умолчанию 600 = 10 мин)
ENV UPTIME_CHECK_INTERVAL_SEC=600

ENTRYPOINT ["/bin/sh", "-c"]
CMD ["while true; do /app/uptime-check.sh; sleep ${UPTIME_CHECK_INTERVAL_SEC}; done"]
