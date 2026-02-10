/**
 * ADM-01: Вход через Telegram (Telegram Login Widget).
 * Виджет редиректит на /auth/callback с параметрами от Telegram.
 */
import { useEffect, useRef } from 'react'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME || ''

export default function Login() {
  const containerRef = useRef(null)

  useEffect(() => {
    if (!BOT_USERNAME || !containerRef.current) return
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', BOT_USERNAME)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-auth-url', `${window.location.origin}/auth/callback`)
    script.setAttribute('data-request-access', 'write')
    script.async = true
    containerRef.current.appendChild(script)
    return () => {
      if (containerRef.current && script.parentNode) script.remove()
    }
  }, [])

  return (
    <div className="login-page">
      <h1>Вход для администратора</h1>
      <p>Войдите через Telegram. Доступ только для пользователей из белого списка.</p>
      {BOT_USERNAME ? (
        <div ref={containerRef} />
      ) : (
        <p className="login-error">Не настроен VITE_TELEGRAM_BOT_USERNAME (имя бота для виджета).</p>
      )}
    </div>
  )
}
