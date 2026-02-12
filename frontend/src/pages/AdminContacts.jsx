/**
 * ADM-03: Форма добавления контакта администратором (SR-ADM03-001..005).
 * Каскадный выбор помещения (FE-03) + поля контакта + позиция ОСС.
 * Капча не требуется; авторизация — JWT. Статус «валидирован» устанавливается бэкендом.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAuth } from '../App'

const API = '/api/premises'

export default function AdminContacts() {
  const navigate = useNavigate()
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('mkd_access_token') : null

  // --- Каскадные фильтры (как в Premises.jsx) ---
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

  const [loading, setLoading] = useState(false)
  const [filterLoading, setFilterLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [errors, setErrors] = useState({})

  // Редирект если нет токена
  useEffect(() => {
    if (!token) navigate('/login', { replace: true })
  }, [token, navigate])

  // --- Каскад: подъезды ---
  useEffect(() => {
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
      .catch(() => {
        setEntrances([])
        setHasEntrances(false)
      })
      .finally(() => setFilterLoading(false))
  }, [])

  // --- Каскад: этажи ---
  useEffect(() => {
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
  }, [entrance, hasEntrances])

  // --- Каскад: типы ---
  useEffect(() => {
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
  }, [floor, entrance])

  // --- Каскад: номера ---
  useEffect(() => {
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
  }, [floor, type, entrance])

  // --- Отправка ---
  const handleSubmit = async (e) => {
    e.preventDefault()
    setMessage(null)
    setErrors({})

    if (!selectedPremise) {
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
      const res = await fetch('/api/admin/contacts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          premise_id: selectedPremise.premise_id,
          is_owner: isOwner,
          phone: phone.trim() || null,
          email: email.trim() || null,
          telegram_id: telegramId.trim() || null,
          barrier_vote: isOwner ? (barrierVote || null) : null,
          vote_format: isOwner ? (voteFormat || null) : null,
          registered_ed: isOwner ? (registeredEd || null) : null,
        }),
      })

      const data = await res.json().catch(() => ({}))

      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }

      if (res.ok) {
        setMessage({ type: 'success', text: `Контакт создан (id: ${data.contact_id}, статус: ${data.status})` })
        // Сбросить поля контакта после успеха
        setIsOwner(true); setPhone(''); setEmail(''); setTelegramId('')
        setBarrierVote(''); setVoteFormat(''); setRegisteredEd('')
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

  return (
    <div className="admin-contacts-page">
      <h1>Добавить контакт</h1>
      <p className="admin-hint">Ввод контакта от имени администратора. Статус «валидирован» устанавливается автоматически.</p>

      {/* --- Каскадный выбор помещения --- */}
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

        <button type="submit" disabled={loading}>{loading ? 'Сохранение…' : 'Сохранить контакт'}</button>
      </form>

      {message && (
        <div className={`form-message ${message.type}`} role="alert">
          {message.text}
        </div>
      )}
    </div>
  )
}
