/**
 * ADM-04: Управление белым списком администраторов (только super_administrator).
 * Список админов, добавление, удаление, установка логина/пароля.
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAuth } from '../App'
import TelegramIcon from '../components/TelegramIcon'

function getToken() {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('mkd_access_token')
}

function getSubFromToken(t) {
  if (!t) return null
  try {
    const payload = JSON.parse(atob(t.split('.')[1]))
    return payload.sub || null
  } catch {
    return null
  }
}

export default function SuperadminAdmins() {
  const navigate = useNavigate()
  const token = getToken()
  const currentSub = getSubFromToken(token)
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [addForm, setAddForm] = useState({ telegram_id: '', login: '', password: '' })
  const [adding, setAdding] = useState(false)
  const [patchRow, setPatchRow] = useState(null)
  const [patchForm, setPatchForm] = useState({ login: '', password: '' })
  const [patching, setPatching] = useState(false)

  const fetchList = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/superadmin/admins', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setList(Array.isArray(data) ? data : [])
      } else {
        setError(typeof data.detail === 'string' ? data.detail : 'Доступ запрещён (только суперадмин)')
      }
    } catch (err) {
      setError(err.message || 'Ошибка сети')
    } finally {
      setLoading(false)
    }
  }, [token, navigate])

  useEffect(() => {
    if (!token) {
      navigate('/login', { replace: true })
      return
    }
    fetchList()
  }, [token, navigate, fetchList])

  const handleAdd = async (e) => {
    e.preventDefault()
    const tid = addForm.telegram_id.trim()
    if (!tid) return
    setAdding(true)
    setError(null)
    try {
      const body = { telegram_id: tid, role: 'administrator' }
      if (addForm.login.trim()) body.login = addForm.login.trim()
      if (addForm.password) body.password = addForm.password
      const res = await fetch('/api/superadmin/admins', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setAddForm({ telegram_id: '', login: '', password: '' })
        fetchList()
      } else {
        setError(typeof data.detail === 'string' ? data.detail : 'Ошибка добавления')
      }
    } catch (err) {
      setError(err.message || 'Ошибка сети')
    } finally {
      setAdding(false)
    }
  }

  const handleDelete = async (telegramId) => {
    if (!window.confirm(`Удалить администратора ${telegramId} из белого списка?`)) return
    setError(null)
    try {
      const res = await fetch(`/api/superadmin/admins/${encodeURIComponent(telegramId)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        fetchList()
      } else {
        setError(typeof data.detail === 'string' ? data.detail : 'Ошибка удаления')
      }
    } catch (err) {
      setError(err.message || 'Ошибка сети')
    }
  }

  const handlePatch = async (e) => {
    e.preventDefault()
    if (!patchRow) return
    const loginVal = patchForm.login.trim()
    const hasPassword = patchForm.password.length >= 8
    setPatching(true)
    setError(null)
    try {
      const body = { login: loginVal || '' }
      if (hasPassword) body.password = patchForm.password
      const res = await fetch(`/api/superadmin/admins/${encodeURIComponent(patchRow.telegram_id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setPatchRow(null)
        setPatchForm({ login: '', password: '' })
        fetchList()
      } else {
        setError(typeof data.detail === 'string' ? data.detail : 'Ошибка сохранения')
      }
    } catch (err) {
      setError(err.message || 'Ошибка сети')
    } finally {
      setPatching(false)
    }
  }

  if (!token) return null

  /** Ссылка на чат с админом по Telegram ID */
  const telegramChatUrl = (telegramId) => (telegramId ? `tg://user?id=${String(telegramId).trim()}` : null)

  return (
    <div className="superadmin-admins-page">
      <h1>Управление администраторами</h1>
      <p className="superadmin-admins-hint">Только для суперадмина: белый список админов (Telegram ID). Можно задать логин и пароль для входа без Telegram.</p>
      {error && <p className="superadmin-admins-error">{error}</p>}

      <section className="superadmin-add-form">
        <h2>Добавить администратора</h2>
        <form onSubmit={handleAdd}>
          <label>
            Telegram ID <span className="required">*</span>
            <input
              type="text"
              value={addForm.telegram_id}
              onChange={(e) => setAddForm((p) => ({ ...p, telegram_id: e.target.value }))}
              placeholder="123456789"
              disabled={adding}
            />
          </label>
          <label>
            Логин (необязательно)
            <input
              type="text"
              value={addForm.login}
              onChange={(e) => setAddForm((p) => ({ ...p, login: e.target.value }))}
              placeholder="логин для входа"
              disabled={adding}
            />
          </label>
          <label>
            Пароль (необязательно, не короче 8 символов)
            <input
              type="password"
              value={addForm.password}
              onChange={(e) => setAddForm((p) => ({ ...p, password: e.target.value }))}
              placeholder="••••••••"
              disabled={adding}
            />
          </label>
          <button type="submit" disabled={adding}>{adding ? 'Добавление…' : 'Добавить'}</button>
        </form>
      </section>

      <section className="superadmin-list">
        <h2>Список администраторов</h2>
        {loading && <p>Загрузка…</p>}
        {!loading && list.length === 0 && <p className="superadmin-empty">Нет записей.</p>}
        {!loading && list.length > 0 && (
          <table className="superadmin-admins-table">
            <thead>
              <tr>
                <th>Telegram ID</th>
                <th title="Чат в Telegram">ТГ</th>
                <th>Роль</th>
                <th>Текущий логин</th>
                <th>Добавлен</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {list.map((a) => (
                <tr key={a.telegram_id}>
                  <td>{a.telegram_id}</td>
                  <td>
                    {telegramChatUrl(a.telegram_id) && (
                      <a href={telegramChatUrl(a.telegram_id)} target="_blank" rel="noopener noreferrer" className="link-telegram-chat" title="Написать в Telegram">
                        <TelegramIcon width={20} height={20} />
                      </a>
                    )}
                  </td>
                  <td>{a.role === 'super_administrator' ? 'Суперадмин' : 'Администратор'}</td>
                  <td>{a.login ?? '—'}</td>
                  <td>{a.created_at ? new Date(a.created_at).toLocaleDateString('ru-RU') : '—'}</td>
                  <td>
                    <button
                      type="button"
                      className="superadmin-btn-set-pwd"
                      onClick={() => {
                        if (patchRow?.telegram_id === a.telegram_id) {
                          setPatchRow(null)
                          setPatchForm({ login: '', password: '' })
                        } else {
                          setPatchRow(a)
                          setPatchForm({ login: a.login ?? '', password: '' })
                        }
                      }}
                    >
                      {patchRow?.telegram_id === a.telegram_id ? 'Отмена' : 'Логин/пароль'}
                    </button>
                    <button
                      type="button"
                      className="superadmin-btn-delete"
                      onClick={() => handleDelete(a.telegram_id)}
                      disabled={a.telegram_id === currentSub}
                      title={a.telegram_id === currentSub ? 'Нельзя удалить себя' : 'Удалить из списка'}
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {patchRow && (
        <section className="superadmin-patch-form">
          <h2>Логин и пароль для {patchRow.telegram_id}</h2>
          <p className="superadmin-patch-hint">Текущий логин отображается ниже. Очистите поле логина и сохраните — логин и пароль будут удалены, вход только через Telegram.</p>
          <form onSubmit={handlePatch}>
            <label>
              Логин (очистите, чтобы отключить вход по логину/паролю)
              <input
                type="text"
                value={patchForm.login}
                onChange={(e) => setPatchForm((p) => ({ ...p, login: e.target.value }))}
                placeholder="текущий логин"
                disabled={patching}
              />
            </label>
            <label>
              Пароль (не короче 8 символов; при очистке логина пароль тоже удаляется)
              <input
                type="password"
                value={patchForm.password}
                onChange={(e) => setPatchForm((p) => ({ ...p, password: e.target.value }))}
                placeholder="оставьте пустым, чтобы не менять"
                disabled={patching}
              />
            </label>
            <button type="submit" disabled={patching}>{patching ? 'Сохранение…' : 'Сохранить'}</button>
            <button type="button" onClick={() => { setPatchRow(null); setPatchForm({ login: '', password: '' }) }}>Отмена</button>
          </form>
        </section>
      )}
    </div>
  )
}
