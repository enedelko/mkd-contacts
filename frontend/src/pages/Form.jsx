/**
 * FE-04: Форма сбора данных (анкета) — SR-FE04-001..011.
 * Помещение, «Я собственник», контакт (телефон/Telegram/email), позиция ОСС, согласия, капча Turnstile.
 */
import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''
const POLICY_URL = import.meta.env.VITE_POLICY_URL || '/policy'

export default function Form() {
  const location = useLocation()
  const navigate = useNavigate()
  const premise = location.state?.premise
  const premiseLabel = location.state ? `${location.state.entrance} / ${location.state.floor} / ${location.state.type} № ${premise?.number}` : ''

  const [isOwner, setIsOwner] = useState(true)
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [telegramId, setTelegramId] = useState('')
  const [voteFor, setVoteFor] = useState(true)
  const [voteFormat, setVoteFormat] = useState('electronic')
  const [registeredEd, setRegisteredEd] = useState(false)
  const [consent, setConsent] = useState(false)
  const [captchaToken, setCaptchaToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [errors, setErrors] = useState({})

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
    if (!premise) return
    const hasContact = phone.trim() || email.trim() || telegramId.trim()
    if (!hasContact) {
      setErrors({ contact: 'Укажите хотя бы один контакт: телефон, email или Telegram' })
      return
    }
    if (!consent) {
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
          vote_for: voteFor,
          vote_format: voteFormat,
          registered_ed: registeredEd,
          consent_version: '1.0',
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
        <label>
          <input type="checkbox" checked={isOwner} onChange={(e) => setIsOwner(e.target.checked)} />
          Я собственник (обязательно)
        </label>

        <fieldset>
          <legend>Контакт (хотя бы одно поле)</legend>
          <label>
            Телефон
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+7 ..." />
          </label>
          {errors.phone && <span className="field-error">{errors.phone}</span>}
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          {errors.email && <span className="field-error">{errors.email}</span>}
          <label>
            Telegram (id или @username)
            <input type="text" value={telegramId} onChange={(e) => setTelegramId(e.target.value)} />
          </label>
          {errors.telegram_id && <span className="field-error">{errors.telegram_id}</span>}
          {errors.contact && <span className="field-error">{errors.contact}</span>}
        </fieldset>

        <label>
          Позиция по ОСС: ЗА
          <select value={String(voteFor)} onChange={(e) => setVoteFor(e.target.value === 'true')}>
            <option value="true">Да</option>
            <option value="false">Нет</option>
          </select>
        </label>

        <label>
          Формат голосования
          <select value={voteFormat} onChange={(e) => setVoteFormat(e.target.value)}>
            <option value="paper">Бумага</option>
            <option value="electronic">Электронно</option>
          </select>
        </label>

        <label>
          <input type="checkbox" checked={registeredEd} onChange={(e) => setRegisteredEd(e.target.checked)} />
          Зарегистрирован в Электронном Доме
        </label>

        <label>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          Даю согласие на обработку персональных данных. <a href={POLICY_URL} target="_blank" rel="noopener noreferrer">Политика конфиденциальности</a>
        </label>
        {errors.consent && <span className="field-error">{errors.consent}</span>}

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
        </div>
      )}
    </div>
  )
}
