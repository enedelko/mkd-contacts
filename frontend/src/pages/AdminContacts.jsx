/**
 * ADM-03: Форма добавления / редактирования контакта администратором.
 * Создание: /admin/contacts — каскадный выбор помещения + POST.
 * Редактирование: /admin/contacts/:id — загрузка данных + PUT.
 */
import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { clearAuth } from '../App'

const API = '/api/premises'

export default function AdminContacts() {
  const navigate = useNavigate()
  const { id: editId } = useParams()
  const isEdit = Boolean(editId)
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('mkd_access_token') : null

  // --- Каскадные фильтры ---
  const [hasEntrances, setHasEntrances] = useState(null)
  const [entrances, setEntrances] = useState([])
  const [floors, setFloors] = useState([])
  const [types, setTypes] = useState([])
  const [premises, setPremises] = useState([])
  const [entrance, setEntrance] = useState('')
  const [floor, setFloor] = useState('')
  const [type, setType] = useState('')
  const [selectedPremise, setSelectedPremise] = useState(null)

  // --- Поля контакта ---
  const [isOwner, setIsOwner] = useState(true)
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [telegramId, setTelegramId] = useState('')
  const [barrierVote, setBarrierVote] = useState('')
  const [voteFormat, setVoteFormat] = useState('')
  const [registeredEd, setRegisteredEd] = useState('')

  // --- Данные для отображения помещения в режиме редактирования ---
  const [editPremiseLabel, setEditPremiseLabel] = useState('')
  const [editPremiseId, setEditPremiseId] = useState('')

  const [loading, setLoading] = useState(false)
  const [filterLoading, setFilterLoading] = useState(false)
  const [editLoading, setEditLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [errors, setErrors] = useState({})

  // Редирект если нет токена
  useEffect(() => {
    if (!token) navigate('/login', { replace: true })
  }, [token, navigate])

  // --- Загрузка контакта в режиме редактирования ---
  useEffect(() => {
    if (!isEdit || !token) return
    setEditLoading(true)
    fetch(`/api/admin/contacts/${editId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (r.status === 401 || r.status === 403) { clearAuth(); navigate('/login', { replace: true }); return null }
        if (!r.ok) throw new Error('Контакт не найден')
        return r.json()
      })
      .then((data) => {
        if (!data) return
        setIsOwner(data.is_owner ?? true)
        setPhone(data.phone || '')
        setEmail(data.email || '')
        setTelegramId(data.telegram_id || '')
        setBarrierVote(data.barrier_vote || '')
        setVoteFormat(data.vote_format || '')
        setRegisteredEd(data.registered_ed || '')
        setEditPremiseId(data.premise_id || '')
        const parts = []
        if (data.entrance) parts.push(`подъезд ${data.entrance}`)
        if (data.floor) parts.push(`этаж ${data.floor}`)
        if (data.premises_type && data.premises_number) parts.push(`${data.premises_type} № ${data.premises_number}`)
        setEditPremiseLabel(parts.length ? parts.join(', ') : data.premise_id)
      })
      .catch((err) => setMessage({ type: 'error', text: err.message }))
      .finally(() => setEditLoading(false))
  }, [isEdit, editId, token, navigate])

  // --- Каскад: подъезды (только в режиме создания) ---
  useEffect(() => {
    if (isEdit) return
    setFilterLoading(true)
    fetch(`${API}/entrances`)
      .then((r) => r.json())
      .then((d) => {
        const list = d.entrances || []
        setEntrances(list)
        setHasEntrances(list.length > 0)
        if (list.length === 0) {
          return fetch(`${API}/floors`)
            .then((r) => r.json())
            .then((d) => setFloors(d.floors || []))
        }
      })
      .catch(() => { setEntrances([]); setHasEntrances(false) })
      .finally(() => setFilterLoading(false))
  }, [isEdit])

  // --- Каскад: этажи ---
  useEffect(() => {
    if (isEdit) return
    if (hasEntrances === null || !hasEntrances) return
    if (!entrance) {
      setFloors([]); setFloor(''); setType(''); setTypes([]); setPremises([]); setSelectedPremise(null)
      return
    }
    setFilterLoading(true)
    fetch(`${API}/floors?entrance=${encodeURIComponent(entrance)}`)
      .then((r) => r.json())
      .then((d) => setFloors(d.floors || []))
      .catch(() => setFloors([]))
      .finally(() => setFilterLoading(false))
    setFloor(''); setType(''); setTypes([]); setPremises([]); setSelectedPremise(null)
  }, [entrance, hasEntrances, isEdit])

  // --- Каскад: типы ---
  useEffect(() => {
    if (isEdit) return
    if (!floor) { setTypes([]); setType(''); setPremises([]); setSelectedPremise(null); return }
    setFilterLoading(true)
    const params = new URLSearchParams({ floor })
    if (entrance) params.set('entrance', entrance)
    fetch(`${API}/types?${params}`)
      .then((r) => r.json())
      .then((d) => setTypes(d.types || []))
      .catch(() => setTypes([]))
      .finally(() => setFilterLoading(false))
    setType(''); setPremises([]); setSelectedPremise(null)
  }, [floor, entrance, isEdit])

  // --- Каскад: номера ---
  useEffect(() => {
    if (isEdit) return
    if (!floor || !type) { setPremises([]); setSelectedPremise(null); return }
    setFilterLoading(true)
    const params = new URLSearchParams({ floor, type })
    if (entrance) params.set('entrance', entrance)
    fetch(`${API}/numbers?${params}`)
      .then((r) => r.json())
      .then((d) => setPremises(d.premises || []))
      .catch(() => setPremises([]))
      .finally(() => setFilterLoading(false))
    setSelectedPremise(null)
  }, [floor, type, entrance, isEdit])

  // --- Отправка ---
  const handleSubmit = async (e) => {
    e.preventDefault()
    setMessage(null)
    setErrors({})

    if (!isEdit && !selectedPremise) {
      setErrors({ premise: 'Выберите помещение' })
      return
    }
    const hasContact = phone.trim() || email.trim() || telegramId.trim()
    if (!hasContact) {
      setErrors({ contact: 'Укажите хотя бы один контакт: телефон, email или Telegram' })
      return
    }

    setLoading(true)
    try {
      const url = isEdit ? `/api/admin/contacts/${editId}` : '/api/admin/contacts'
      const method = isEdit ? 'PUT' : 'POST'
      const bodyData = {
        is_owner: isOwner,
        phone: phone.trim() || null,
        email: email.trim() || null,
        telegram_id: telegramId.trim() || null,
        barrier_vote: isOwner ? (barrierVote || null) : null,
        vote_format: isOwner ? (voteFormat || null) : null,
        registered_ed: isOwner ? (registeredEd || null) : null,
      }
      if (!isEdit) bodyData.premise_id = selectedPremise.premise_id

      const res = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(bodyData),
      })

      const data = await res.json().catch(() => ({}))

      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }

      if (res.ok) {
        if (isEdit) {
          setMessage({ type: 'success', text: 'Контакт обновлён' })
        } else {
          setMessage({ type: 'success', text: `Контакт создан (id: ${data.contact_id}, статус: ${data.status})` })
          setIsOwner(true); setPhone(''); setEmail(''); setTelegramId('')
          setBarrierVote(''); setVoteFormat(''); setRegisteredEd('')
        }
      } else {
        const errorText = typeof data.detail === 'string'
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail.map((e) => e.msg || JSON.stringify(e)).join('; ')
            : 'Ошибка сохранения'
        setMessage({ type: 'error', text: errorText })
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Ошибка сети' })
    } finally {
      setLoading(false)
    }
  }

  const premiseLabel = selectedPremise
    ? [
        hasEntrances ? `подъезд ${entrance}` : null,
        `этаж ${floor}`,
        `${type} № ${selectedPremise.number}`,
      ].filter(Boolean).join(', ')
    : null

  const isEmpty = hasEntrances !== null && entrances.length === 0 && floors.length === 0 && !filterLoading

  if (editLoading) return <div className="admin-contacts-page"><h1>Загрузка…</h1></div>

  return (
    <div className="admin-contacts-page">
      <h1>{isEdit ? `Редактирование контакта #${editId}` : 'Добавить контакт'}</h1>
      <p className="admin-hint">
        {isEdit
          ? `Помещение: ${editPremiseLabel}`
          : 'Ввод контакта от имени администратора. Статус «валидирован» устанавливается автоматически.'}
      </p>

      {/* --- Каскадный выбор помещения (только при создании) --- */}
      {!isEdit && (
        <fieldset>
          <legend>Помещение</legend>
          {hasEntrances === null && <p>Загрузка…</p>}
          {isEmpty && <p className="empty-message">Данные по дому пока не загружены.</p>}
          {!isEmpty && hasEntrances !== null && (
            <div className="cascade-filters">
              {hasEntrances && (
                <label>
                  Подъезд
                  <select value={entrance} onChange={(e) => setEntrance(e.target.value)} disabled={filterLoading}>
                    <option value="">— выберите —</option>
                    {entrances.map((e) => (
                      <option key={e} value={e}>{e}</option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                Этаж
                <select
                  value={floor}
                  onChange={(e) => setFloor(e.target.value)}
                  disabled={(hasEntrances && !entrance) || filterLoading || floors.length === 0}
                >
                  <option value="">— выберите —</option>
                  {floors.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </label>
              <label>
                Тип помещения
                <select value={type} onChange={(e) => setType(e.target.value)} disabled={!floor || filterLoading}>
                  <option value="">— выберите —</option>
                  {types.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </label>
              <label>
                Номер помещения
                <select
                  value={selectedPremise ? selectedPremise.premise_id : ''}
                  onChange={(e) => {
                    const p = premises.find((x) => x.premise_id === e.target.value)
                    setSelectedPremise(p || null)
                  }}
                  disabled={!type || filterLoading}
                >
                  <option value="">— выберите —</option>
                  {premises.map((p) => (
                    <option key={p.premise_id} value={p.premise_id}>
                      {p.number}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          {errors.premise && <span className="field-error">{errors.premise}</span>}
          {premiseLabel && <p className="selected-info">Выбрано: {premiseLabel}</p>}
        </fieldset>
      )}

      {/* --- Форма --- */}
      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Статус</legend>
          <label>
            <input type="radio" name="ownerStatus" value="owner" checked={isOwner} onChange={() => { setIsOwner(true) }} />
            Собственник помещения
          </label>
          <label>
            <input type="radio" name="ownerStatus" value="resident" checked={!isOwner} onChange={() => { setIsOwner(false); setBarrierVote(''); setVoteFormat(''); setRegisteredEd('') }} />
            Проживающий (не собственник)
          </label>
        </fieldset>

        <fieldset>
          <legend>Контактные данные (хотя бы одно поле)</legend>
          <label>
            Телефон:{' '}
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+7 ..." />
          </label>
          {errors.phone && <span className="field-error">{errors.phone}</span>}
          <label>
            Email:{' '}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          {errors.email && <span className="field-error">{errors.email}</span>}
          <label>
            Telegram (id или @username):{' '}
            <input type="text" value={telegramId} onChange={(e) => setTelegramId(e.target.value)} />
          </label>
          {errors.telegram_id && <span className="field-error">{errors.telegram_id}</span>}
          {errors.contact && <span className="field-error">{errors.contact}</span>}
        </fieldset>

        {/* --- Вопросы ОСС (только для собственников) --- */}
        {isOwner && (
          <fieldset>
            <legend>Позиция по ОСС</legend>
            <p>Отношение к схеме размещения шлагбаумов:</p>
            <label>
              <input type="radio" name="barrierVote" value="for" checked={barrierVote === 'for'} onChange={() => setBarrierVote('for')} />
              За
            </label>
            <label>
              <input type="radio" name="barrierVote" value="against" checked={barrierVote === 'against'} onChange={() => setBarrierVote('against')} />
              Против
            </label>
            <label>
              <input type="radio" name="barrierVote" value="undecided" checked={barrierVote === 'undecided'} onChange={() => setBarrierVote('undecided')} />
              Не определился(-ась)
            </label>

            <p>Планируемый формат голосования:</p>
            <label>
              <input type="radio" name="voteFormat" value="electronic" checked={voteFormat === 'electronic'} onChange={() => setVoteFormat('electronic')} />
              Онлайн в Электронном доме
            </label>
            <label>
              <input type="radio" name="voteFormat" value="paper" checked={voteFormat === 'paper'} onChange={() => setVoteFormat('paper')} />
              На бумажном бюллетене
            </label>
            <label>
              <input type="radio" name="voteFormat" value="undecided" checked={voteFormat === 'undecided'} onChange={() => setVoteFormat('undecided')} />
              Не определился(-ась)
            </label>

            <p>Зарегистрирован(-а) в <a href="https://ed.mos.ru/about-oss/" target="_blank" rel="noopener noreferrer">Электронном доме</a>:</p>
            <label>
              <input type="radio" name="registeredEd" value="yes" checked={registeredEd === 'yes'} onChange={() => setRegisteredEd('yes')} />
              Да
            </label>
            <label>
              <input type="radio" name="registeredEd" value="no" checked={registeredEd === 'no'} onChange={() => setRegisteredEd('no')} />
              Нет
            </label>
          </fieldset>
        )}

        <button type="submit" disabled={loading}>
          {loading ? 'Сохранение…' : isEdit ? 'Сохранить изменения' : 'Сохранить контакт'}
        </button>
        {isEdit && (
          <button type="button" style={{ marginLeft: '0.5rem' }} onClick={() => navigate('/admin/contacts/list')}>
            Назад к списку
          </button>
        )}
      </form>

      {message && (
        <div className={`form-message ${message.type}`} role="alert">
          {message.text}
        </div>
      )}
    </div>
  )
}
