/**
 * ADM-01: Вход через Telegram.
 * Редирект в текущем окне на oauth.telegram.org; после входа Telegram возвращает на /auth/callback.
 */
import { useState, useEffect } from 'react'

export default function Login() {
  const [botId, setBotId] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/auth/telegram/bot-id')
      .then((r) => r.json())
      .then((data) => {
        if (data.bot_id != null) setBotId(data.bot_id)
        else setError(data.detail || 'Бот не настроен')
      })
      .catch(() => setError('Сервер недоступен'))
      .finally(() => setLoading(false))
  }, [])

  const goToTelegram = () => {
    if (!botId) return
    setError(null)
    const origin = window.location.origin
    const returnTo = `${origin}/auth/callback`
    window.location.href = `https://oauth.telegram.org/auth?bot_id=${botId}&origin=${encodeURIComponent(origin)}&request_access=write&return_to=${encodeURIComponent(returnTo)}`
  }

  return (
    <div className="login-page">
      <h1>Вход для администратора</h1>
      <p>Войдите через Telegram. Доступ только для пользователей из белого списка.</p>
      {loading && <p>Загрузка…</p>}
      {error && <p className="login-error">{error}</p>}
      {!loading && botId && (
        <button type="button" className="login-telegram-btn" onClick={goToTelegram}>
          Войти через Telegram
        </button>
      )}
      {!loading && !botId && !error && <p className="login-error">Бот не настроен (TELEGRAM_BOT_TOKEN).</p>}
    </div>
  )
}
