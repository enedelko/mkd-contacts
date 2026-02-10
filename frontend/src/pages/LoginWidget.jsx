/**
 * ADM-01: Страница с Telegram Login Widget (redirect).
 * Открывается в popup; после авторизации Telegram редиректит на /auth/callback с hash и id в URL.
 * Используем виджет с data-auth-url вместо oauth.telegram.org (который возвращает только tgAuthResult без hash).
 */
import { useEffect, useRef, useState } from 'react'

export default function LoginWidget() {
  const containerRef = useRef(null)
  const [error, setError] = useState(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    fetch('/api/auth/telegram/bot-id')
      .then((r) => r.json())
      .then((data) => {
        const username = data.bot_username
        if (!username) {
          setError(data.detail || 'Бот не настроен')
          return
        }
        const authUrl = `${window.location.origin}/auth/callback`
        const script = document.createElement('script')
        script.async = true
        script.src = 'https://telegram.org/js/telegram-widget.js?22'
        script.setAttribute('data-telegram-login', username)
        script.setAttribute('data-size', 'large')
        script.setAttribute('data-auth-url', authUrl)
        script.setAttribute('data-request-access', 'write')
        script.onload = () => setLoaded(true)
        if (containerRef.current) {
          containerRef.current.appendChild(script)
        }
      })
      .catch(() => setError('Сервер недоступен'))
  }, [])

  return (
    <div className="login-widget-page" style={{ padding: '1rem', textAlign: 'center' }}>
      <h2>Вход через Telegram</h2>
      {error && <p className="login-error">{error}</p>}
      <div ref={containerRef} />
      {!error && !loaded && <p>Загрузка…</p>}
    </div>
  )
}
