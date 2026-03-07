/**
 * BE-03: Просмотр аудит-лога для администратора.
 * SR-BE03-008..014: фильтры по дате/entity_id, подписи, ссылки.
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { clearAuth } from '../App'
import TelegramIcon from '../components/TelegramIcon'
import { checkConsentRedirect } from '../utils/adminApi'

const ACTION_LABELS = {
  insert: 'Создание',
  update: 'Обновление',
  delete: 'Удаление',
  select: 'Просмотр',
  status_change: 'Смена статуса',
  premise_removed: 'Отвязка помещения',
  bot_answers_update: 'Обновление (бот)',
  forget: 'Удаление данных',
  password_change: 'Смена пароля',
  policy_consent: 'Согласие с политикой',
  export: 'Экспорт',
}

const ENTITY_TYPE_LABELS = {
  contact: 'Контакт',
  admin: 'Админ',
  bot_alias: 'Бот-алиас',
  contacts_template: 'Шаблон контактов',
}

const FIELD_LABELS = {
  phone: 'телефон',
  email: 'email',
  telegram_id: 'Telegram',
  how_to_address: 'обращение',
  is_owner: 'собственник',
  barrier_vote: 'голос (шлагбаум)',
  vote_format: 'формат голосования',
  registered_in_ed: 'Электронный Дом',
}

const PAGE_SIZE = 50

function formatNewValue(action, newValue) {
  if (action === 'update' && !newValue) {
    return <em className="audit-no-details">подробности не зафиксированы</em>
  }
  if (action === 'update' && newValue && /^[a-z_,]+$/.test(newValue)) {
    const labels = newValue.split(',').map(f => FIELD_LABELS[f] || f)
    return `Изменены: ${labels.join(', ')}`
  }
  return newValue || '—'
}

function telegramChatUrl(telegramId) {
  if (!telegramId || String(telegramId).trim() === '') return null
  return `tg://user?id=${String(telegramId).trim()}`
}

export default function AuditLog() {
  const navigate = useNavigate()
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('mkd_access_token') : null

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState(null)
  const [offset, setOffset] = useState(0)

  const [filterEntity, setFilterEntity] = useState('')
  const [filterAction, setFilterAction] = useState('')
  const [filterUser, setFilterUser] = useState('')
  const [filterEntityId, setFilterEntityId] = useState('')
  const [filterFromDate, setFilterFromDate] = useState('')
  const [filterToDate, setFilterToDate] = useState('')

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
      if (filterEntityId.trim()) params.set('entity_id', filterEntityId.trim())
      if (filterFromDate) params.set('from_date', filterFromDate)
      if (filterToDate) params.set('to_date', filterToDate)
      params.set('limit', String(PAGE_SIZE))
      params.set('offset', String(offset))

      const res = await fetch(`/api/admin/audit?${params}`, {
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
  }, [token, filterEntity, filterAction, filterUser, filterEntityId, filterFromDate, filterToDate, offset, navigate])

  useEffect(() => {
    fetchAudit()
  }, [fetchAudit])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  function buildFilterParams() {
    const params = new URLSearchParams()
    if (filterEntity) params.set('entity_type', filterEntity)
    if (filterAction) params.set('action', filterAction)
    if (filterUser.trim()) params.set('user_id', filterUser.trim())
    if (filterEntityId.trim()) params.set('entity_id', filterEntityId.trim())
    if (filterFromDate) params.set('from_date', filterFromDate)
    if (filterToDate) params.set('to_date', filterToDate)
    return params
  }

  async function handleExport() {
    if (!token) return
    setExporting(true)
    try {
      const params = buildFilterParams()
      const res = await fetch(`/api/admin/audit/export?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        setError('Ошибка экспорта')
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'audit_log.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message || 'Ошибка экспорта')
    } finally {
      setExporting(false)
    }
  }

  function renderEntityCell(a) {
    const isContactLink = a.entity_type === 'contact' && a.entity_id && /^\d+$/.test(a.entity_id)
    const label = a.entity_label || a.entity_id || '—'
    if (isContactLink) {
      return (
        <td className="entity-id-cell" title={`ID контакта: ${a.entity_id}`}>
          <Link to={`/admin/contacts/${a.entity_id}`}>{label}</Link>
        </td>
      )
    }
    return (
      <td className="entity-id-cell" title={a.entity_id}>
        {label.length > 30 ? label.slice(0, 30) + '…' : label}
      </td>
    )
  }

  function renderUserCell(a) {
    const effectiveId = a.user_id || a.user_id_resolved
    const tgUrl = telegramChatUrl(effectiveId)
    const label = a.user_label || (a.user_id ? a.user_id : null)

    if (!effectiveId) {
      return <td className="user-cell">аноним</td>
    }
    return (
      <td className="user-cell" title={`Telegram ID: ${effectiveId}`}>
        {label && <span className="user-name">{label}</span>}
        {tgUrl && (
          <a href={tgUrl} target="_blank" rel="noopener noreferrer" className="link-telegram-chat" title="Написать в Telegram">
            <TelegramIcon width={18} height={18} />
          </a>
        )}
        {!label && !tgUrl && effectiveId}
      </td>
    )
  }

  return (
    <div className="audit-log-page">
      <h1>Аудит-лог</h1>

      <div className="filters-bar">
        <label>
          Сущность:
          <select value={filterEntity} onChange={(e) => { setFilterEntity(e.target.value); setOffset(0) }}>
            <option value="">Все</option>
            {Object.entries(ENTITY_TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
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
            placeholder="Telegram ID"
          />
        </label>
        <label>
          ID записи:
          <input
            type="text"
            value={filterEntityId}
            onChange={(e) => setFilterEntityId(e.target.value)}
            placeholder="ID контакта"
          />
        </label>
        <label>
          С даты:
          <input
            type="date"
            value={filterFromDate}
            onChange={(e) => { setFilterFromDate(e.target.value); setOffset(0) }}
          />
        </label>
        <label>
          По дату:
          <input
            type="date"
            value={filterToDate}
            onChange={(e) => { setFilterToDate(e.target.value); setOffset(0) }}
          />
        </label>
        <button type="button" onClick={() => { setOffset(0); fetchAudit() }} disabled={loading}>
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
        <button type="button" onClick={handleExport} disabled={exporting || loading} className="export-btn">
          {exporting ? 'Экспорт…' : 'Экспорт в Excel'}
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
              <th>Запись</th>
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
                <td className="audit-time-cell">{a.created_at ? new Date(a.created_at).toLocaleString('ru-RU') : '—'}</td>
                <td>{ENTITY_TYPE_LABELS[a.entity_type] || a.entity_type}</td>
                {renderEntityCell(a)}
                <td><span className={`action-badge ${a.action}`}>{ACTION_LABELS[a.action] || a.action}</span></td>
                <td>{a.old_value || '—'}</td>
                <td>{formatNewValue(a.action, a.new_value)}</td>
                {renderUserCell(a)}
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
