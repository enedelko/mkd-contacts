# BE-01: Frontend — React (Vite) бандл, отдача через Nginx (SR-BE01-004)
# Stage 1: build
FROM node:20-alpine AS builder

# Имя бота для Telegram Login Widget (подставляется в бандл при сборке)
ARG VITE_TELEGRAM_BOT_USERNAME
ENV VITE_TELEGRAM_BOT_USERNAME=$VITE_TELEGRAM_BOT_USERNAME

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# Stage 2: serve
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
