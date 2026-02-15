/**
 * ADM-01: Вход через логин/пароль или Telegram.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Login() {
  const navigate = useNavigate()
  const [botId, setBotId] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loginForm, setLoginForm] = useState({ login: '', password: '' })
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    fetch('/api/auth/telegram/bot-id')
      .then((r) => r.json())
      .then((data) => {
        if (data.bot_id != null) setBotId(data.bot_id)
        else {
          const errMsg = typeof data.detail === 'string'
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((e) => e.msg || JSON.stringify(e)).join('; ')
              : 'Бот не настроен'
          setError(errMsg)
        }
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

  const onLoginSubmit = (e) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login: loginForm.login.trim(), password: loginForm.password }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.access_token) {
          localStorage.setItem('mkd_access_token', data.access_token)
          window.dispatchEvent(new CustomEvent('mkd-auth-change'))
          fetch('/api/auth/consent-status', {
            headers: { Authorization: `Bearer ${data.access_token}` },
          })
            .then((res) => res.json())
            .then((status) => {
              if (status.policy_consent_accepted) {
                navigate('/', { replace: true })
              } else {
                navigate('/admin/consent', { replace: true })
              }
            })
            .catch(() => navigate('/', { replace: true }))
        } else {
          setError(typeof data.detail === 'string' ? data.detail : 'Неверный логин или пароль')
        }
      })
      .catch(() => setError('Ошибка сети'))
      .finally(() => setSubmitting(false))
  }

  return (
    <div className="login-page">
      <h1>Вход для администратора</h1>
      <p>Войдите по логину и паролю или через Telegram. Доступ только для пользователей из белого списка.</p>
      {error && <p className="login-error">{error}</p>}

      <form className="login-form" onSubmit={onLoginSubmit}>
        <label>
          Логин
          <input
            type="text"
            autoComplete="username"
            value={loginForm.login}
            onChange={(e) => setLoginForm((prev) => ({ ...prev, login: e.target.value }))}
            disabled={submitting}
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            autoComplete="current-password"
            value={loginForm.password}
            onChange={(e) => setLoginForm((prev) => ({ ...prev, password: e.target.value }))}
            disabled={submitting}
          />
        </label>
        <button type="submit" className="login-password-btn" disabled={submitting}>
          {submitting ? 'Вход…' : 'Войти по логину и паролю'}
        </button>
      </form>

      {!loading && botId && (
        <>
          <p className="login-separator">или</p>
          <button type="button" className="login-telegram-btn" onClick={goToTelegram}>
            Войти через Telegram
          </button>
        </>
      )}
      {!loading && !botId && !error && <p className="login-error">Бот не настроен (TELEGRAM_BOT_TOKEN).</p>}
    </div>
  )
}
