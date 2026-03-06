/**
 * CORE-03 / ADM-02: Список контактов для модерации.
 * Список только после выбора подъезда (кнопки); поиск по номеру помещения, фильтры IP/даты; по клику по строке — просмотр.
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { clearAuth } from '../App'
import TelegramIcon from '../components/TelegramIcon'
import EntrancePicker from '../components/EntrancePicker'
import { checkConsentRedirect } from '../utils/adminApi'

const STATUS_LABELS = { pending: 'Ожидает', validated: 'Валидирован', inactive: 'Неактуальный' }
const STATUS_OPTIONS = ['pending', 'validated', 'inactive']

const BARRIER_VOTE_LABELS = { for: 'ЗА', against: 'Против', undecided: 'Не определился' }
const VOTE_FORMAT_LABELS = { electronic: 'Электронно', paper: 'Бумага', undecided: 'Не определился' }
// Поддержка старых значений yes/no/true/false и новых none/account/owner
const REGISTERED_ED_LABELS = {
  none: 'Нет ЭД / нет данных',
  account: 'ЭД без подтверждённой собственности',
  owner: 'Собственность подтверждена в ЭД',
  yes: 'Собственность подтверждена в ЭД',
  no: 'Нет ЭД / нет данных',
  true: 'Собственность подтверждена в ЭД',
  false: 'Нет ЭД / нет данных',
}

export default function AdminContactsList() {
  const navigate = useNavigate()
  const location = useLocation()
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('mkd_access_token') : null

  const [selectedEntrance, setSelectedEntrance] = useState(
    location.state?.entrance ?? null
  )

  const [contacts, setContacts] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [filterPremisesNumber, setFilterPremisesNumber] = useState(
    location.state?.premises_number ?? ''
  )
  const [filterStatus, setFilterStatus] = useState('')
  const [filterIp, setFilterIp] = useState('')
  const [filterFrom, setFilterFrom] = useState('')
  const [filterTo, setFilterTo] = useState('')

  const [selected, setSelected] = useState(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)

  useEffect(() => {
    if (!token) navigate('/login', { replace: true })
  }, [token, navigate])

  const fetchContacts = useCallback(async () => {
    if (!token || !selectedEntrance) return
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      params.set('entrance', selectedEntrance)
      if (filterPremisesNumber.trim()) params.set('premises_number', filterPremisesNumber.trim())
      if (filterStatus) params.set('status', filterStatus)
      if (filterIp.trim()) params.set('ip', filterIp.trim())
      if (filterFrom) params.set('from_date', filterFrom)
      if (filterTo) params.set('to_date', filterTo)
      const res = await fetch(`/api/admin/contacts?${params}`, {
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
  }, [token, selectedEntrance, filterPremisesNumber, filterStatus, filterIp, filterFrom, filterTo, navigate])

  useEffect(() => {
    if (selectedEntrance) fetchContacts()
    else {
      setContacts([])
      setTotal(0)
      setError(null)
    }
  }, [selectedEntrance, fetchContacts])

  const handleStatusChange = async (contactId, newStatus, e) => {
    e?.stopPropagation()
    if (!token || contactId == null || contactId === -1) return
    try {
      const res = await fetch(`/api/admin/contacts/${contactId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status: newStatus }),
      })
      const { redirectConsent, dataFor403 } = await checkConsentRedirect(res, navigate)
      if (redirectConsent) return
      if (dataFor403 !== undefined || res.status === 401 || res.status === 403) {
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

  const toggleSelect = (id, e) => {
    e?.stopPropagation()
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = (e) => {
    e?.stopPropagation()
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
        body: JSON.stringify({ contact_ids: [...selected].filter((id) => typeof id === 'number' && id > 0), status: newStatus }),
      })
      const { redirectConsent, dataFor403 } = await checkConsentRedirect(res, navigate)
      if (redirectConsent) return
      if (dataFor403 !== undefined || res.status === 401 || res.status === 403) {
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
    if (c.premises_type && c.premises_number) {
      parts.push(`${c.premises_type} ${c.premises_number}`)
    } else if (c.premises_number) {
      parts.push(c.premises_number)
    } else if (c.premises_type) {
      parts.push(c.premises_type)
    }
    return parts.length ? parts.join(', ') : c.premise_id
  }

  const onRowClick = (contactId) => {
    navigate(`/admin/contacts/${contactId}`, { state: { fromEntrance: selectedEntrance } })
  }

  const telegramLink = (telegramId) => {
    if (!telegramId || !String(telegramId).trim()) return null
    const id = String(telegramId).trim()
    if (/^\d+$/.test(id)) return `tg://user?id=${id}`
    return `https://t.me/${id.replace(/^@/, '')}`
  }

  const telegramLinkByPhone = (phone) => {
    if (!phone || !String(phone).trim()) return null
    let digits = String(phone).replace(/\D/g, '')
    if (digits.length < 10) return null
    if (digits.startsWith('8') && digits.length === 11) digits = '7' + digits.slice(1)
    if (digits.startsWith('7') && digits.length === 11) return `https://t.me/+${digits}`
    if (digits.length >= 10) return `https://t.me/+${digits}`
    return null
  }

  if (!selectedEntrance) {
    return (
      <div className="admin-contacts-list-page">
        <h1>Контакты</h1>
        <EntrancePicker
          selected={null}
          onSelect={(ent) => setSelectedEntrance(ent)}
          onReset={() => setSelectedEntrance(null)}
          prompt="Выберите подъезд, чтобы увидеть список контактов."
          emptyMessage="Нет данных о подъездах. Загрузите реестр."
        />
      </div>
    )
  }

  return (
    <div className="admin-contacts-list-page">
      <h1>Контакты</h1>

      <EntrancePicker
        selected={selectedEntrance}
        onSelect={(ent) => setSelectedEntrance(ent)}
        onReset={() => setSelectedEntrance(null)}
        barExtra={<Link to="/upload" className="btn-link" state={{ entrance: selectedEntrance }}>Сформировать шаблон</Link>}
      />

      <div className="filters-bar">
        <label>
          Номер квартиры/помещения:
          <input
            type="text"
            value={filterPremisesNumber}
            onChange={(e) => setFilterPremisesNumber(e.target.value)}
            placeholder="№"
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
        <label>
          IP:
          <input
            type="text"
            value={filterIp}
            onChange={(e) => setFilterIp(e.target.value)}
            placeholder="Фильтр по IP"
          />
        </label>
        <label>
          Дата с:
          <input
            type="date"
            value={filterFrom}
            onChange={(e) => setFilterFrom(e.target.value)}
          />
        </label>
        <label>
          Дата по:
          <input
            type="date"
            value={filterTo}
            onChange={(e) => setFilterTo(e.target.value)}
          />
        </label>
        <button type="button" onClick={fetchContacts} disabled={loading}>
          {loading ? 'Загрузка…' : 'Обновить'}
        </button>
      </div>

      {error && <p className="list-error">{error}</p>}

      <p className="total-info">Найдено: {total}</p>

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
              <th>Помещение</th>
              <th>Статус</th>
              <th className="col-tg">ТГ</th>
              <th>Обращение</th>
              <th>Телефон</th>
              <th>Email</th>
              <th className="col-owner">Собств.</th>
              <th>IP</th>
              <th>Шлагбаумы</th>
              <th>Голосование</th>
              <th>Эл. дом</th>
              <th>Создан</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((c, index) => (
              <tr
                key={c.is_canary ? `canary-${index}` : c.id}
                className={`status-${c.status} clickable-row row-stripe-${index % 4}`}
                onClick={() => onRowClick(c.id)}
              >
                <td onClick={(e) => toggleSelect(c.id, e)}>
                  <input type="checkbox" checked={selected.has(c.id)} onChange={() => {}} />
                </td>
                <td title={c.premise_id}>{premiseLabel(c)}</td>
                <td>
                  <span className={`status-badge ${c.status}`}>{STATUS_LABELS[c.status] || c.status}</span>
                </td>
                <td onClick={(e) => e.stopPropagation()} className="col-tg">
                  {(c.telegram_id && telegramLink(c.telegram_id)) || (c.phone && telegramLinkByPhone(c.phone)) ? (
                    <a
                      href={telegramLink(c.telegram_id) || telegramLinkByPhone(c.phone)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-icon-link"
                      title={c.telegram_id ? 'Открыть в Telegram' : 'Написать по номеру телефона'}
                    >
                      <TelegramIcon width={20} height={20} />
                    </a>
                  ) : '—'}
                </td>
                <td>{c.how_to_address || '—'}</td>
                <td>{c.phone || '—'}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  {c.email ? (
                    <a href={`mailto:${c.email}`} className="btn-icon-link" title="Написать письмо">📧</a>
                  ) : '—'}
                </td>
                <td className="col-owner">{c.is_owner ? 'Да' : 'Нет'}</td>
                <td>{c.ip || '—'}</td>
                <td>{c.barrier_vote ? (BARRIER_VOTE_LABELS[c.barrier_vote] ?? c.barrier_vote) : '—'}</td>
                <td>{c.vote_format ? (VOTE_FORMAT_LABELS[c.vote_format] ?? c.vote_format) : '—'}</td>
                <td>{c.registered_ed ? (REGISTERED_ED_LABELS[c.registered_ed] ?? c.registered_ed) : '—'}</td>
                <td>{c.created_at ? new Date(c.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '—'}</td>
                <td className="actions" onClick={(e) => e.stopPropagation()}>
                  <Link to={`/admin/contacts/${c.id}`} state={{ fromEntrance: selectedEntrance }} className="btn-edit">Редактировать</Link>
                  {c.status !== 'validated' && (
                    <button type="button" className="btn-validate" onClick={(e) => handleStatusChange(c.id, 'validated', e)}>
                      Валидировать
                    </button>
                  )}
                  {c.status !== 'pending' && (
                    <button type="button" className="btn-pending" onClick={(e) => handleStatusChange(c.id, 'pending', e)}>
                      Сбросить
                    </button>
                  )}
                  {c.status !== 'inactive' && (
                    <button type="button" className="btn-inactive" onClick={(e) => handleStatusChange(c.id, 'inactive', e)}>
                      Неактуальный
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!loading && selectedEntrance && contacts.length === 0 && !error && (
        <p className="empty-message">В выбранном подъезде контакты не найдены.</p>
      )}
    </div>
  )
}
