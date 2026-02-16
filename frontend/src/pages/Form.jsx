/**
 * FE-04: Форма сбора данных (анкета) — SR-FE04-001..011.
 * Помещение, «Я собственник», контакт (телефон/Telegram/email), позиция ОСС, согласия, капча Turnstile.
 */
import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { formatPhoneOnBlur } from '../utils/phoneFormat'
import { entranceButtonLabel } from '../utils/entranceLabel'

const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''
const POLICY_URL = import.meta.env.VITE_POLICY_URL || '/policy'

export default function Form() {
  const location = useLocation()
  const navigate = useNavigate()
  const premise = location.state?.premise
  const premiseLabel = location.state
    ? [
        location.state.hasEntrances ? entranceButtonLabel(location.state.entrance || '—') : null,
        `Этаж ${location.state.floor}`,
        `${location.state.type} № ${premise?.number}`,
      ].filter(Boolean).join(' / ')
    : ''

  const [isOwner, setIsOwner] = useState(true)
  const handleOwnerChange = (val) => {
    setIsOwner(val)
    if (!val) { setBarrierVote(''); setVoteFormat(''); setRegisteredEd('') }
  }
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [telegramId, setTelegramId] = useState('')
  const [barrierVote, setBarrierVote] = useState('')
  const [voteFormat, setVoteFormat] = useState('')
  const [registeredEd, setRegisteredEd] = useState('')
  const [consent, setConsent] = useState(false)
  const [captchaToken, setCaptchaToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [errors, setErrors] = useState({})
  const [admins, setAdmins] = useState([])

  useEffect(() => {
    if (!premise && !location.state) {
      navigate('/premises', { replace: true })
    }
  }, [premise, location.state, navigate])

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return
    window.__mkdTurnstileCallback = (token) => setCaptchaToken(token || '')
    const id = 'turnstile-script'
    if (document.getElementById(id)) return
    const s = document.createElement('script')
    s.id = id
    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js'
    s.async = true
    document.head.appendChild(s)
    return () => {
      delete window.__mkdTurnstileCallback
      const el = document.getElementById(id)
      if (el) el.remove()
    }
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setMessage(null)
    setErrors({})
    setAdmins([])
    if (!premise) return
    const hasContact = phone.trim() || email.trim() || telegramId.trim()
    const hasOssAnswers = !!(barrierVote || voteFormat || registeredEd)
    if (!hasContact && (!isOwner || !hasOssAnswers)) {
      const msg = isOwner
        ? 'Укажите контакт или ответьте на вопросы по предстоящему ОСС'
        : 'Укажите хотя бы один контакт: телефон, email или Telegram'
      setErrors({ contact: msg })
      return
    }
    if (hasContact && !consent) {
      setErrors({ consent: 'Необходимо согласие на обработку ПДн' })
      return
    }
    if (TURNSTILE_SITE_KEY && !captchaToken) {
      setErrors({ captcha: 'Пройдите проверку капчи' })
      return
    }
    setLoading(true)
    try {
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          premise_id: premise.premise_id,
          is_owner: isOwner,
          phone: phone.trim() || null,
          email: email.trim() || null,
          telegram_id: telegramId.trim() || null,
          barrier_vote: isOwner ? (barrierVote || null) : null,
          vote_format: isOwner ? (voteFormat || null) : null,
          registered_ed: isOwner ? (registeredEd || null) : null,
          consent_version: hasContact ? '1.0' : 'IP',
          captcha_token: captchaToken || null,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok && data.success) {
        setMessage({ type: 'success', text: data.message || 'Данные приняты' })
      } else {
        const errorText = typeof data.detail === 'string'
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail.map((e) => e.msg || JSON.stringify(e)).join('; ')
            : 'Ошибка отправки'
        setMessage({ type: 'error', text: errorText })
        if (data.errors) {
          const byField = {}
          data.errors.forEach((err) => { byField[err.field] = err.message })
          setErrors(byField)
        }
        if (res.status === 403 && Array.isArray(data.admins)) {
          setAdmins(data.admins)
        }
        if (res.status === 429) {
          setMessage({ type: 'error', text: 'Превышен лимит отправок. Повторите позже.' })
        }
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Ошибка сети' })
    } finally {
      setLoading(false)
    }
  }

  if (!premise) return null

  return (
    <div className="form-page">
      <h1>Анкета</h1>
      <p className="premise-display">Помещение: {premiseLabel}</p>

      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Статус</legend>
          <label>
            <input type="radio" name="ownerStatus" value="owner" checked={isOwner} onChange={() => handleOwnerChange(true)} />
            Собственник помещения
          </label>
          <label>
            <input type="radio" name="ownerStatus" value="resident" checked={!isOwner} onChange={() => handleOwnerChange(false)} />
            Проживающий (не собственник)
          </label>
        </fieldset>

        <fieldset>
          <legend>Контакт</legend>
          {isOwner && <p className="hint">Заполните, если хотите, чтобы с вами можно было связаться. Без контактов голос будет анонимным.</p>}
          <label>
            Телефон:{' '}
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              onBlur={(e) => setPhone(formatPhoneOnBlur(e.target.value))}
              placeholder="+7 ..."
            />
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
          {(phone.trim() || email.trim() || telegramId.trim()) && (
            <label>
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              Даю согласие на обработку персональных данных. <a href={POLICY_URL} target="_blank" rel="noopener noreferrer">Политика конфиденциальности</a>
            </label>
          )}
          {errors.consent && <span className="field-error">{errors.consent}</span>}
        </fieldset>

        {isOwner && (
          <fieldset>
            <legend>Вопросы по предстоящему ОСС</legend>
            <p>Одобряю <a href="https://t.me/SILVERINFO/4304" target="_blank" rel="noopener noreferrer">схему размещения шлагбаумов</a>:</p>
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
              Ещё не определились
            </label>

            <p>Как вы проголосуете:</p>
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
              Ещё не определились
            </label>

            <p>Зарегистрированы ли вы в <a href="https://ed.mos.ru/about-oss/" target="_blank" rel="noopener noreferrer">Электронном доме</a>?</p>
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

        {TURNSTILE_SITE_KEY && (
          <div className="turnstile-wrap">
            <div className="cf-turnstile" data-sitekey={TURNSTILE_SITE_KEY} data-callback="__mkdTurnstileCallback" />
            {errors.captcha && <span className="field-error">{errors.captcha}</span>}
          </div>
        )}

        <button type="submit" disabled={loading}>{loading ? 'Отправка…' : 'Отправить'}</button>
      </form>

      {message && (
        <div className={`form-message ${message.type}`} role="alert">
          {message.text}
          {admins.length > 0 && (
            <ul className="admin-list">
              {admins.map((a, i) => (
                <li key={i}>{a.full_name} ({a.premises})</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
