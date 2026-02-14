/**
 * BE-03: Просмотр аудит-лога для администратора.
 * Фильтрация по типу сущности, действию, пользователю. Пагинация.
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAuth } from '../App'

const ACTION_LABELS = {
  insert: 'Создание',
  update: 'Обновление',
  delete: 'Удаление',
  select: 'Просмотр',
  status_change: 'Смена статуса',
}

const PAGE_SIZE = 50

export default function AuditLog() {
  const navigate = useNavigate()
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('mkd_access_token') : null

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [offset, setOffset] = useState(0)

  // Фильтры
  const [filterEntity, setFilterEntity] = useState('')
  const [filterAction, setFilterAction] = useState('')
  const [filterUser, setFilterUser] = useState('')

  useEffect(() => {
    if (!token) navigate('/login', { replace: true })
  }, [token, navigate])

  const fetchAudit = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (filterEntity) params.set('entity_type', filterEntity)
      if (filterAction) params.set('action', filterAction)
      if (filterUser.trim()) params.set('user_id', filterUser.trim())
      params.set('limit', String(PAGE_SIZE))
      params.set('offset', String(offset))
      const res = await fetch(`/api/admin/audit?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setItems(data.items || [])
        setTotal(data.total || 0)
      } else {
        setError(typeof data.detail === 'string' ? data.detail : 'Ошибка загрузки')
      }
    } catch (err) {
      setError(err.message || 'Ошибка сети')
    } finally {
      setLoading(false)
    }
  }, [token, filterEntity, filterAction, filterUser, offset, navigate])

  useEffect(() => {
    fetchAudit()
  }, [fetchAudit])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div className="audit-log-page">
      <h1>Аудит-лог</h1>

      <div className="filters-bar">
        <label>
          Сущность:
          <select value={filterEntity} onChange={(e) => { setFilterEntity(e.target.value); setOffset(0) }}>
            <option value="">Все</option>
            <option value="contact">Контакт</option>
            <option value="premise">Помещение</option>
          </select>
        </label>
        <label>
          Действие:
          <select value={filterAction} onChange={(e) => { setFilterAction(e.target.value); setOffset(0) }}>
            <option value="">Все</option>
            {Object.entries(ACTION_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Пользователь:
          <input
            type="text"
            value={filterUser}
            onChange={(e) => setFilterUser(e.target.value)}
            placeholder="ID пользователя"
          />
        </label>
        <button type="button" onClick={() => { setOffset(0); fetchAudit() }} disabled={loading}>
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
      </div>

      {error && <p className="list-error">{error}</p>}

      <p className="total-info">Записей: {total}</p>

      {items.length > 0 && (
        <table className="audit-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Время</th>
              <th>Сущность</th>
              <th>ID записи</th>
              <th>Действие</th>
              <th>Старое</th>
              <th>Новое</th>
              <th>Пользователь</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}>
                <td>{a.id}</td>
                <td>{a.created_at ? new Date(a.created_at).toLocaleString('ru-RU') : '—'}</td>
                <td>{a.entity_type}</td>
                <td className="entity-id-cell" title={a.entity_id}>{a.entity_id?.length > 20 ? a.entity_id.slice(0, 20) + '…' : a.entity_id || '—'}</td>
                <td><span className={`action-badge ${a.action}`}>{ACTION_LABELS[a.action] || a.action}</span></td>
                <td>{a.old_value || '—'}</td>
                <td>{a.new_value || '—'}</td>
                <td>{a.user_id || '—'}</td>
                <td>{a.ip || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {totalPages > 1 && (
        <div className="pagination">
          <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            ← Назад
          </button>
          <span>Стр. {currentPage} из {totalPages}</span>
          <button type="button" disabled={currentPage >= totalPages} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Вперёд →
          </button>
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <p className="empty-message">Записей не найдено.</p>
      )}
    </div>
  )
}
