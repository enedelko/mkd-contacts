/**
 * ADM-01: Вход через Telegram.
 * Открываем oauth.telegram.org в новом окне (popup) или в этой вкладке — без iframe, без CSP.
 * Telegram возвращает tgAuthResult (без hash); при наличии hash обрабатываем в AuthCallback.
 */
import { useState, useEffect, useCallback } from 'react'

const POPUP_WIDTH = 500
const POPUP_HEIGHT = 600

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

  const handleMessage = useCallback((event) => {
    if (event.origin !== window.location.origin) return
    if (event.data?.type !== 'mkd-telegram-auth' || !event.data?.params) return
    const qs = new URLSearchParams(event.data.params)
    if (event.data.rawTgAuthResult) qs.set('tg_auth_result', event.data.rawTgAuthResult)
    fetch(`/api/auth/telegram/callback?${qs.toString()}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.access_token) {
          localStorage.setItem('mkd_access_token', data.access_token)
          window.dispatchEvent(new CustomEvent('mkd-auth-change'))
          window.location.href = '/'
        } else {
          setError(data.detail || 'Ошибка входа')
        }
      })
      .catch((err) => setError(err.message || 'Ошибка сети'))
  }, [])

  useEffect(() => {
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [handleMessage])

  const getOAuthUrl = () => {
    const origin = window.location.origin
    const returnTo = `${origin}/auth/callback`
    return `https://oauth.telegram.org/auth?bot_id=${botId}&origin=${encodeURIComponent(origin)}&request_access=write&return_to=${encodeURIComponent(returnTo)}`
  }

  const openPopup = () => {
    if (!botId) return
    setError(null)
    const left = Math.round((window.screen.width - POPUP_WIDTH) / 2)
    const top = Math.round((window.screen.height - POPUP_HEIGHT) / 2)
    window.open(
      getOAuthUrl(),
      'telegram_oauth',
      `width=${POPUP_WIDTH},height=${POPUP_HEIGHT},left=${left},top=${top},scrollbars=yes`
    )
  }

  const openInSameTab = () => {
    if (!botId) return
    setError(null)
    window.location.href = getOAuthUrl()
  }

  return (
    <div className="login-page">
      <h1>Вход для администратора</h1>
      <p>Войдите через Telegram. Доступ только для пользователей из белого списка.</p>
      {loading && <p>Загрузка…</p>}
      {error && <p className="login-error">{error}</p>}
      {!loading && botId && (
        <>
          <button type="button" className="login-telegram-btn" onClick={openPopup}>
            Войти через Telegram
          </button>
          <p style={{ marginTop: 8 }}>
            <button type="button" className="link-style" onClick={openInSameTab}>
              Открыть в этой вкладке (отладка)
            </button>
          </p>
        </>
      )}
      {!loading && !botId && !error && <p className="login-error">Бот не настроен (TELEGRAM_BOT_TOKEN).</p>}
    </div>
  )
}
