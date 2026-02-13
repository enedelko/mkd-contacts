/**
 * VAL-01: Список контактов для модерации — просмотр и смена статуса.
 * Фильтрация по помещению и статусу. Расшифрованные ПДн приходят с сервера.
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { clearAuth } from '../App'

const STATUS_LABELS = { pending: 'Ожидает', validated: 'Валидирован', inactive: 'Неактуальный' }
const STATUS_OPTIONS = ['pending', 'validated', 'inactive']

export default function AdminContactsList() {
  const navigate = useNavigate()
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('mkd_access_token') : null

  const [contacts, setContacts] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Фильтры
  const [filterPremise, setFilterPremise] = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  // Массовые действия (CORE-03)
  const [selected, setSelected] = useState(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)

  useEffect(() => {
    if (!token) navigate('/login', { replace: true })
  }, [token, navigate])

  const fetchContacts = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (filterPremise.trim()) params.set('premise_id', filterPremise.trim())
      if (filterStatus) params.set('status', filterStatus)
      const res = await fetch(`/api/admin/contacts?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setContacts(data.contacts || [])
        setTotal(data.total || 0)
      } else {
        setError(typeof data.detail === 'string' ? data.detail : 'Ошибка загрузки')
      }
    } catch (err) {
      setError(err.message || 'Ошибка сети')
    } finally {
      setLoading(false)
    }
  }, [token, filterPremise, filterStatus, navigate])

  useEffect(() => {
    fetchContacts()
  }, [fetchContacts])

  const handleStatusChange = async (contactId, newStatus) => {
    if (!token) return
    try {
      const res = await fetch(`/api/admin/contacts/${contactId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status: newStatus }),
      })
      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      if (res.ok) {
        setContacts((prev) =>
          prev.map((c) => (c.id === contactId ? { ...c, status: newStatus } : c))
        )
      } else {
        const data = await res.json().catch(() => ({}))
        alert(typeof data.detail === 'string' ? data.detail : 'Ошибка смены статуса')
      }
    } catch (err) {
      alert(err.message || 'Ошибка сети')
    }
  }

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selected.size === contacts.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(contacts.map((c) => c.id)))
    }
  }

  const handleBulkStatus = async (newStatus) => {
    if (!token || selected.size === 0) return
    if (!confirm(`Изменить статус ${selected.size} контакт(ов) на «${STATUS_LABELS[newStatus]}»?`)) return
    setBulkLoading(true)
    try {
      const res = await fetch('/api/admin/contacts/bulk-status', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ contact_ids: [...selected], status: newStatus }),
      })
      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      if (res.ok) {
        setContacts((prev) =>
          prev.map((c) => (selected.has(c.id) ? { ...c, status: newStatus } : c))
        )
        setSelected(new Set())
      } else {
        const data = await res.json().catch(() => ({}))
        alert(typeof data.detail === 'string' ? data.detail : 'Ошибка массовой смены статуса')
      }
    } catch (err) {
      alert(err.message || 'Ошибка сети')
    } finally {
      setBulkLoading(false)
    }
  }

  const premiseLabel = (c) => {
    const parts = []
    if (c.entrance) parts.push(`п.${c.entrance}`)
    if (c.floor) parts.push(`эт.${c.floor}`)
    if (c.premises_type) parts.push(c.premises_type)
    if (c.premises_number) parts.push(`№${c.premises_number}`)
    return parts.length ? parts.join(', ') : c.premise_id
  }

  return (
    <div className="admin-contacts-list-page">
      <h1>Контакты</h1>

      <div className="filters-bar">
        <label>
          Помещение (кад. №):
          <input
            type="text"
            value={filterPremise}
            onChange={(e) => setFilterPremise(e.target.value)}
            placeholder="77:01:..."
          />
        </label>
        <label>
          Статус:
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
            <option value="">Все</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{STATUS_LABELS[s]}</option>
            ))}
          </select>
        </label>
        <button type="button" onClick={fetchContacts} disabled={loading}>
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
      </div>

      {error && <p className="list-error">{error}</p>}

      <p className="total-info">Найдено: {total}</p>

      {/* CORE-03: панель массовых действий */}
      {selected.size > 0 && (
        <div className="bulk-actions">
          <span>Выбрано: {selected.size}</span>
          <button type="button" className="btn-validate" disabled={bulkLoading} onClick={() => handleBulkStatus('validated')}>
            Валидировать
          </button>
          <button type="button" className="btn-pending" disabled={bulkLoading} onClick={() => handleBulkStatus('pending')}>
            Сбросить
          </button>
          <button type="button" className="btn-inactive" disabled={bulkLoading} onClick={() => handleBulkStatus('inactive')}>
            Неактуальный
          </button>
          <button type="button" disabled={bulkLoading} onClick={() => setSelected(new Set())}>
            Снять выделение
          </button>
        </div>
      )}

      {contacts.length > 0 && (
        <table className="contacts-table">
          <thead>
            <tr>
              <th><input type="checkbox" checked={contacts.length > 0 && selected.size === contacts.length} onChange={toggleSelectAll} /></th>
              <th>ID</th>
              <th>Помещение</th>
              <th>Статус</th>
              <th>Собственник</th>
              <th>Телефон</th>
              <th>Email</th>
              <th>Telegram</th>
              <th>Шлагбаумы</th>
              <th>Голосование</th>
              <th>Эл. дом</th>
              <th>Создан</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((c) => (
              <tr key={c.id} className={`status-${c.status}`}>
                <td><input type="checkbox" checked={selected.has(c.id)} onChange={() => toggleSelect(c.id)} /></td>
                <td>{c.id}</td>
                <td title={c.premise_id}>{premiseLabel(c)}</td>
                <td>
                  <span className={`status-badge ${c.status}`}>{STATUS_LABELS[c.status] || c.status}</span>
                </td>
                <td>{c.is_owner ? 'Да' : 'Нет'}</td>
                <td>{c.phone || '—'}</td>
                <td>{c.email || '—'}</td>
                <td>{c.telegram_id || '—'}</td>
                <td>{c.barrier_vote || '—'}</td>
                <td>{c.vote_format || '—'}</td>
                <td>{c.registered_ed || '—'}</td>
                <td>{c.created_at ? new Date(c.created_at).toLocaleDateString('ru-RU') : '—'}</td>
                <td className="actions">
                  <Link to={`/admin/contacts/${c.id}`} className="btn-edit">Редактировать</Link>
                  {c.status !== 'validated' && (
                    <button type="button" className="btn-validate" onClick={() => handleStatusChange(c.id, 'validated')}>
                      Валидировать
                    </button>
                  )}
                  {c.status !== 'pending' && (
                    <button type="button" className="btn-pending" onClick={() => handleStatusChange(c.id, 'pending')}>
                      Сбросить
                    </button>
                  )}
                  {c.status !== 'inactive' && (
                    <button type="button" className="btn-inactive" onClick={() => handleStatusChange(c.id, 'inactive')}>
                      Неактуальный
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!loading && contacts.length === 0 && !error && (
        <p className="empty-message">Контакты не найдены.</p>
      )}
    </div>
  )
}
