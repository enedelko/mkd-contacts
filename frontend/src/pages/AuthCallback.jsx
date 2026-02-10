/**
 * ADM-01: Callback после редиректа от Telegram Login Widget.
 * Читает query-параметры, запрашивает JWT у backend, сохраняет токен и редиректит на главную.
 */
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

export default function AuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState(null)

  useEffect(() => {
    const hash = searchParams.get('hash')
    const id = searchParams.get('id')
    if (!hash || !id) {
      setError('Нет данных от Telegram')
      return
    }
    const query = searchParams.toString()
    fetch(`/api/auth/telegram/callback?${query}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.access_token) {
          localStorage.setItem('mkd_access_token', data.access_token)
          window.dispatchEvent(new CustomEvent('mkd-auth-change'))
          navigate('/', { replace: true })
        } else {
          setError(data.detail || 'Ошибка входа')
        }
      })
      .catch((err) => setError(err.message || 'Ошибка сети'))
  }, [searchParams, navigate])

  if (error) {
    return (
      <div className="auth-callback-page">
        <p className="auth-error">{error}</p>
        <a href="/">На главную</a>
      </div>
    )
  }
  return (
    <div className="auth-callback-page">
      <p>Вход…</p>
    </div>
  )
}
