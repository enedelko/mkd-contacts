/**
 * ADM-01: Callback после редиректа от Telegram OAuth.
 * Поддерживаем форматы:
 * - query: ?hash=...&id=...
 * - hash: #hash=...&id=...
 * - tgAuthResult: #tgAuthResult=<base64> (JSON с полями id, hash, auth_date, first_name и т.д.)
 * Если открыто в popup — передаём параметры в окно-родитель; окно закрывается только по кнопке.
 */
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

function parseTgAuthResult(base64Str) {
  if (!base64Str || typeof atob !== 'function') return null
  try {
    const json = atob(base64Str.replace(/-/g, '+').replace(/_/g, '/'))
    const obj = JSON.parse(json)
    if (obj && typeof obj.id !== 'undefined') return obj
    return null
  } catch {
    return null
  }
}

function getTelegramParams(searchParams) {
  let hash = searchParams.get('hash')
  let id = searchParams.get('id')
  if (hash && id) return Object.fromEntries([...searchParams.entries()])
  const hashPart = typeof window !== 'undefined' ? window.location.hash?.slice(1) : ''
  if (!hashPart) return null
  const fromHash = new URLSearchParams(hashPart)
  hash = fromHash.get('hash')
  id = fromHash.get('id')
  if (hash && id) return Object.fromEntries([...fromHash.entries()])
  const tgAuthResult = fromHash.get('tgAuthResult')
  if (tgAuthResult) {
    const obj = parseTgAuthResult(tgAuthResult)
    if (obj) {
      const params = { ...obj }
      if (params.hash && params.id) return params
      if (params.id != null) {
        params.id = String(params.id)
        return params
      }
    }
  }
  return null
}

export default function AuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState(null)
  const [popupStatus, setPopupStatus] = useState(null) // 'sent' | null

  useEffect(() => {
    const params = getTelegramParams(searchParams)
    if (!params) {
      setError('Нет данных от Telegram (проверьте URL: query, hash или tgAuthResult)')
      return
    }
    if (!params.hash && params.id) {
      setError(
        'Telegram OAuth вернул данные без подписи (hash). Сервер не может проверить вход. ' +
        'Используйте кнопку «Войти через Telegram» в этом же окне или попробуйте снова.'
      )
      return
    }
    if (!params.hash || !params.id) {
      setError('Не хватает данных от Telegram (нужны hash и id)')
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
