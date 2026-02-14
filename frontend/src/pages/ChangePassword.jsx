/**
 * Смена пароля для текущего администратора.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
function getToken() {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('mkd_access_token')
}

export default function ChangePassword() {
  const navigate = useNavigate()
  const token = getToken()
  const [form, setForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (!token) {
    navigate('/login', { replace: true })
    return null
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    setError(null)
    if (form.new_password !== form.confirm_password) {
      setError('Новый пароль и подтверждение не совпадают')
      return
    }
    if (form.new_password.length < 8) {
      setError('Новый пароль должен быть не короче 8 символов')
      return
    }
    setSubmitting(true)
    fetch('/api/auth/change-password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        current_password: form.current_password,
        new_password: form.new_password,
      }),
    })
      .then((r) => {
        if (r.status === 204) {
          setSuccess(true)
          setForm({ current_password: '', new_password: '', confirm_password: '' })
          return
        }
        return r.json().then((data) => {
          setError(typeof data.detail === 'string' ? data.detail : 'Ошибка смены пароля')
        })
      })
      .catch(() => setError('Ошибка сети'))
      .finally(() => setSubmitting(false))
  }

  if (success) {
    return (
      <div className="change-password-page">
        <h1>Смена пароля</h1>
        <p className="change-password-success">Пароль успешно изменён.</p>
        <p>
          <a href="/">На главную</a>
        </p>
      </div>
    )
  }

  return (
    <div className="change-password-page">
      <h1>Смена пароля</h1>
      <p>Введите текущий пароль и новый пароль (не короче 8 символов).</p>
      {error && <p className="change-password-error">{error}</p>}
      <form onSubmit={handleSubmit}>
        <label>
          Текущий пароль
          <input
            type="password"
            autoComplete="current-password"
            value={form.current_password}
            onChange={(e) => setForm((prev) => ({ ...prev, current_password: e.target.value }))}
            disabled={submitting}
          />
        </label>
        <label>
          Новый пароль
          <input
            type="password"
            autoComplete="new-password"
            value={form.new_password}
            onChange={(e) => setForm((prev) => ({ ...prev, new_password: e.target.value }))}
            disabled={submitting}
          />
        </label>
        <label>
          Подтверждение нового пароля
          <input
            type="password"
            autoComplete="new-password"
            value={form.confirm_password}
            onChange={(e) => setForm((prev) => ({ ...prev, confirm_password: e.target.value }))}
            disabled={submitting}
          />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Сохранение…' : 'Сменить пароль'}
        </button>
      </form>
    </div>
  )
}
