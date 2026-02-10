/**
 * ADM-01: Callback после редиректа от Telegram OAuth.
 * Параметры могут прийти в query (?hash=...&id=...) или в hash (#hash=...&id=...) — учитываем оба варианта.
 * Если открыто в popup (window.opener) — передаём параметры в окно-родитель, показываем статус; окно закрывается только по кнопке (чтобы успеть F12).
 * Иначе — запрашиваем JWT у backend, сохраняем токен и редиректим на главную.
 */
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

function getTelegramParams(searchParams) {
  let hash = searchParams.get('hash')
  let id = searchParams.get('id')
  if (hash && id) return Object.fromEntries([...searchParams.entries()])
  const hashPart = typeof window !== 'undefined' ? window.location.hash?.slice(1) : ''
  if (!hashPart) return null
  const fromHash = new URLSearchParams(hashPart)
  hash = fromHash.get('hash')
  id = fromHash.get('id')
  if (!hash || !id) return null
  return Object.fromEntries([...fromHash.entries()])
}

export default function AuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState(null)
  const [popupStatus, setPopupStatus] = useState(null) // 'sent' | null

  useEffect(() => {
    const params = getTelegramParams(searchParams)
    if (!params) {
      setError('Нет данных от Telegram (проверьте URL: query или hash)')
      return
    }

    if (window.opener) {
      window.opener.postMessage({ type: 'mkd-telegram-auth', params }, window.location.origin)
      setPopupStatus('sent')
      return
    }

    const query = new URLSearchParams(params).toString()
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
  if (popupStatus === 'sent') {
    return (
      <div className="auth-callback-page">
        <p>Данные отправлены в окно входа.</p>
        <p><small>URL: {typeof window !== 'undefined' ? window.location.href : ''}</small></p>
        <button type="button" onClick={() => window.close()}>Закрыть окно</button>
      </div>
    )
  }
  return (
    <div className="auth-callback-page">
      <p>Вход…</p>
    </div>
  )
}
