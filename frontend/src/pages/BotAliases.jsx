/**
 * BOT-01: CRUD-редактор словаря синонимов premise_type_aliases (только super_administrator).
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAuth } from '../App'
import { checkConsentRedirect } from '../utils/adminApi'

function getToken() {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('mkd_access_token')
}

export default function BotAliases() {
  const navigate = useNavigate()
  const token = getToken()
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [addForm, setAddForm] = useState({ premises_type: '', short_name: '', alias: '' })
  const [adding, setAdding] = useState(false)

  const fetchList = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/superadmin/bot-aliases', {
        headers: { Authorization: `Bearer ${token}` },
      })
      const { redirectConsent, dataFor403 } = await checkConsentRedirect(res, navigate)
      if (redirectConsent) return
      if (dataFor403 !== undefined || res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      const data = await res.json().catch(() => [])
      if (res.ok) {
        setList(Array.isArray(data) ? data : [])
      } else {
        setError(typeof data.detail === 'string' ? data.detail : 'Ошибка загрузки')
      }
    } catch (err) {
      setError(err.message || 'Ошибка сети')
    } finally {
      setLoading(false)
    }
  }, [token, navigate])

  useEffect(() => {
    if (!token) { navigate('/login', { replace: true }); return }
    fetchList()
  }, [token, navigate, fetchList])

  const handleAdd = async (e) => {
    e.preventDefault()
    const alias = addForm.alias.trim().toLowerCase()
    if (!alias || !addForm.premises_type.trim() || !addForm.short_name.trim()) return
    setAdding(true)
    setError(null)
    try {
      const res = await fetch('/api/superadmin/bot-aliases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          premises_type: addForm.premises_type.trim(),
          short_name: addForm.short_name.trim(),
          alias,
        }),
      })
      const { redirectConsent, dataFor403 } = await checkConsentRedirect(res, navigate)
      if (redirectConsent) return
      if (dataFor403 !== undefined || res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setAddForm({ premises_type: '', short_name: '', alias: '' })
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

  const handleDelete = async (id, alias) => {
    if (!window.confirm(`Удалить синоним «${alias}»?`)) return
    setError(null)
    try {
      const res = await fetch(`/api/superadmin/bot-aliases/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      const { redirectConsent, dataFor403 } = await checkConsentRedirect(res, navigate)
      if (redirectConsent) return
      if (dataFor403 !== undefined || res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
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

  if (!token) return null

  const grouped = {}
  list.forEach((a) => {
    if (!grouped[a.premises_type]) grouped[a.premises_type] = { short_name: a.short_name, aliases: [] }
    grouped[a.premises_type].aliases.push(a)
  })

  return (
    <div className="superadmin-admins-page">
      <h1>Словарь бота: синонимы типов помещений</h1>
      <p className="superadmin-admins-hint">
        Бот использует эти синонимы для распознавания типа помещения во вводе пользователя.
        Например, «кв» и «квартира» соответствуют типу «Квартира» (сокращение «Кв.»).
      </p>
      {error && <p className="superadmin-admins-error">{error}</p>}

      <section className="superadmin-add-form">
        <h2>Добавить синоним</h2>
        <form onSubmit={handleAdd}>
          <label>
            Тип помещения (точно как в реестре) <span className="required">*</span>
            <input
              type="text"
              value={addForm.premises_type}
              onChange={(e) => setAddForm((p) => ({ ...p, premises_type: e.target.value }))}
              placeholder="Квартира"
              disabled={adding}
            />
          </label>
          <label>
            Сокращение (для кнопок) <span className="required">*</span>
            <input
              type="text"
              value={addForm.short_name}
              onChange={(e) => setAddForm((p) => ({ ...p, short_name: e.target.value }))}
              placeholder="Кв."
              disabled={adding}
            />
          </label>
          <label>
            Синоним (как пишет пользователь) <span className="required">*</span>
            <input
              type="text"
              value={addForm.alias}
              onChange={(e) => setAddForm((p) => ({ ...p, alias: e.target.value }))}
              placeholder="квартиру"
              disabled={adding}
            />
          </label>
          <button type="submit" disabled={adding}>{adding ? 'Добавление…' : 'Добавить'}</button>
        </form>
      </section>

      <section className="superadmin-list">
        <h2>Текущий словарь</h2>
        {loading && <p>Загрузка…</p>}
        {!loading && list.length === 0 && <p className="superadmin-empty">Нет записей.</p>}
        {!loading && Object.entries(grouped).map(([pt, group]) => (
          <div key={pt} style={{ marginBottom: '1.2rem' }}>
            <h3 style={{ margin: '0.5rem 0' }}>{pt} ({group.short_name})</h3>
            <table className="superadmin-admins-table">
              <thead>
                <tr>
                  <th>Синоним</th>
                  <th>Действие</th>
                </tr>
              </thead>
              <tbody>
                {group.aliases.map((a) => (
                  <tr key={a.id}>
                    <td>{a.alias}</td>
                    <td>
                      <button
                        type="button"
                        className="superadmin-btn-delete"
                        onClick={() => handleDelete(a.id, a.alias)}
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </section>
    </div>
  )
}
