/**
 * ADM-09: Страница принятия ответственности за ПДн (Политика конфиденциальности, 152-ФЗ).
 * При первом входе администратор обязан принять согласие; иначе доступ к админ-функциям запрещён.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

function getToken() {
  if (typeof window === 'undefined') return null
  const t = localStorage.getItem('mkd_access_token')
  if (!t) return null
  try {
    const payload = JSON.parse(atob(t.split('.')[1]))
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      localStorage.removeItem('mkd_access_token')
      return null
    }
    return t
  } catch {
    return null
  }
}

export default function AdminConsent() {
  const navigate = useNavigate()
  const [accepted, setAccepted] = useState(false)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!getToken()) {
      navigate('/login', { replace: true })
    }
  }, [navigate])

  const handleSubmit = (e) => {
    e.preventDefault()
    setError(null)
    if (!accepted) {
      setError('Необходимо принять ответственность (отметьте чекбокс)')
      return
    }
    const token = getToken()
    if (!token) {
      navigate('/login', { replace: true })
      return
    }
    setSubmitting(true)
    fetch('/api/auth/consent', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ consent_version: '1.1' }),
    })
      .then((res) => {
        if (res.ok) {
          navigate('/', { replace: true })
          return
        }
        return res.json().then((data) => {
          const msg = typeof data.detail === 'string' ? data.detail : 'Ошибка сохранения согласия'
          setError(msg)
        })
      })
      .catch(() => setError('Ошибка сети'))
      .finally(() => setSubmitting(false))
  }

  const token = getToken()
  if (!token) {
    return null
  }

  return (
    <div className="admin-consent-page policy-page">
      <h1>Принятие ответственности за обработку ПДн</h1>
      <p>
        Вы входите в систему как администратор приложения «Кворум-МКД». В соответствии с Федеральным
        законом № 152-ФЗ «О персональных данных» администраторы несут ответственность за сохранность
        и законность обработки персональных данных в рамках Приложения.
      </p>
      <p>
        Ознакомьтесь с полным текстом:{' '}
        <a href="/policy" target="_blank" rel="noopener noreferrer">
          Политика конфиденциальности
        </a>
      </p>
      <form onSubmit={handleSubmit} className="admin-consent-form">
        <label className="admin-consent-checkbox">
          <input
            type="checkbox"
            checked={accepted}
            onChange={(e) => setAccepted(e.target.checked)}
            disabled={submitting}
          />
          Я принимаю ответственность за сохранность персональных данных и обязуюсь соблюдать
          требования Политики конфиденциальности (152-ФЗ).
        </label>
        {error && <p className="admin-consent-error">{error}</p>}
        <button type="submit" className="admin-consent-submit" disabled={submitting}>
          {submitting ? 'Отправка…' : 'Принять и продолжить'}
        </button>
      </form>
    </div>
  )
}
