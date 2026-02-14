/**
 * LOST-02, ADM-07, ADM-08: Загрузка реестра (суперадмин), загрузка контактов, шаблон по подъезду.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAuth, getRoleFromToken } from '../App'

const EXPECTED_COLUMNS_REGISTER = [
  'cadastral_number', 'area', 'entrance', 'floor', 'premises_type', 'premises_number',
  'phone', 'email', 'telegram_id', 'how_to_address',
]

const EXPECTED_COLUMNS_CONTACTS = [
  'cadastral_number', 'phone', 'email', 'telegram_id', 'how_to_address',
  'is_owner', 'barrier_vote', 'vote_format',
]

export default function Upload() {
  const [fileRegister, setFileRegister] = useState(null)
  const [fileContacts, setFileContacts] = useState(null)
  const [loadingRegister, setLoadingRegister] = useState(false)
  const [loadingContacts, setLoadingContacts] = useState(false)
  const [resultRegister, setResultRegister] = useState(null)
  const [resultContacts, setResultContacts] = useState(null)
  const [structureErrorRegister, setStructureErrorRegister] = useState(null)
  const [structureErrorContacts, setStructureErrorContacts] = useState(null)
  const [entrances, setEntrances] = useState([])
  const [entrance, setEntrance] = useState('')
  const [loadingTemplate, setLoadingTemplate] = useState(false)
  const [templateError, setTemplateError] = useState(null)
  const navigate = useNavigate()

  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('mkd_access_token') : null
  const isSuperAdmin = getRoleFromToken(token) === 'super_administrator'

  useEffect(() => {
    if (!token) return
    fetch('/api/premises/entrances')
      .then((r) => r.json())
      .then((d) => setEntrances(d.entrances || []))
      .catch(() => setEntrances([]))
  }, [token])

  const handleSubmitRegister = async (e) => {
    e.preventDefault()
    if (!fileRegister || !token) {
      setResultRegister({ error: token ? 'Выберите файл' : 'Требуется авторизация' })
      return
    }
    setLoadingRegister(true)
    setResultRegister(null)
    setStructureErrorRegister(null)
    try {
      const formData = new FormData()
      formData.append('file', fileRegister)
      const res = await fetch('/api/admin/import/register', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      const data = await res.json().catch(() => ({}))
      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      if (!res.ok) {
        if (res.status === 400 && data.expected_columns && data.detected_columns) {
          setStructureErrorRegister({ expected: data.expected_columns, detected: data.detected_columns, detail: data.detail })
        } else {
          setResultRegister({ error: typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || res.status) })
        }
        return
      }
      setResultRegister(data)
    } catch (err) {
      setResultRegister({ error: err.message || 'Ошибка сети' })
    } finally {
      setLoadingRegister(false)
    }
  }

  const handleSubmitContacts = async (e) => {
    e.preventDefault()
    if (!fileContacts || !token) {
      setResultContacts({ error: token ? 'Выберите файл' : 'Требуется авторизация' })
      return
    }
    setLoadingContacts(true)
    setResultContacts(null)
    setStructureErrorContacts(null)
    try {
      const formData = new FormData()
      formData.append('file', fileContacts)
      const res = await fetch('/api/admin/import/contacts', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      const data = await res.json().catch(() => ({}))
      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      if (!res.ok) {
        if (res.status === 400 && data.expected_columns && data.detected_columns) {
          setStructureErrorContacts({ expected: data.expected_columns, detected: data.detected_columns, detail: data.detail })
        } else {
          setResultContacts({ error: typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || res.status) })
        }
        return
      }
      setResultContacts(data)
    } catch (err) {
      setResultContacts({ error: err.message || 'Ошибка сети' })
    } finally {
      setLoadingContacts(false)
    }
  }

  const handleDownloadTemplate = async (e) => {
    e.preventDefault()
    if (!entrance || !token) {
      setTemplateError('Выберите подъезд')
      return
    }
    setLoadingTemplate(true)
    setTemplateError(null)
    try {
      const res = await fetch(`/api/admin/import/contacts-template?entrance=${encodeURIComponent(entrance)}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setTemplateError(data.detail || `Ошибка ${res.status}`)
        return
      }
      const blob = await res.blob()
      const disposition = res.headers.get('Content-Disposition')
      const match = disposition && disposition.match(/filename=(.+)/)
      const filename = match ? match[1].replace(/^["']|["']$/g, '') : `contacts_entrance_${entrance}.xlsx`
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = filename
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (err) {
      setTemplateError(err.message || 'Ошибка сети')
    } finally {
      setLoadingTemplate(false)
    }
  }

  return (
    <div className="upload-page">
      <h1>Загрузка данных</h1>

      <section className="instruction" aria-label="Инструкция">
        <p>Форматы: <strong>.csv</strong> (UTF-8, разделитель — точка с запятой), <strong>.xlsx</strong>, <strong>.xls</strong>.</p>
      </section>

      {isSuperAdmin && (
        <section className="upload-section" aria-labelledby="register-heading">
          <h2 id="register-heading">Загрузка реестра (помещения + контакты)</h2>
          <p>Обязательна колонка <strong>кадастровый номер</strong>. Одна строка = одно помещение + опционально один контакт.</p>
          <ul>{EXPECTED_COLUMNS_REGISTER.map((c) => <li key={c}><code>{c}</code></li>)}</ul>
          <form onSubmit={handleSubmitRegister}>
            <label htmlFor="register-file">Файл реестра</label>
            <input id="register-file" type="file" accept=".csv,.xlsx,.xls" onChange={(e) => { setFileRegister(e.target.files?.[0] || null); setResultRegister(null); setStructureErrorRegister(null) }} disabled={!token} />
            <span className="help">{fileRegister ? fileRegister.name : 'Файл не выбран'}</span>
            <button type="submit" disabled={!fileRegister || loadingRegister}>{loadingRegister ? 'Загрузка…' : 'Загрузить реестр'}</button>
          </form>
          {structureErrorRegister && (
            <div className="structure-error" role="alert">
              <h3>Ошибка структуры</h3>
              <p>{structureErrorRegister.detail || 'Набор колонок не совпадает.'}</p>
              <div className="columns-compare">
                <div><strong>Обнаружены:</strong><ul>{structureErrorRegister.detected.map((c, i) => <li key={i}>{c || '(пусто)'}</li>)}</ul></div>
                <div><strong>Ожидаются:</strong><ul>{structureErrorRegister.expected.map((c, i) => <li key={i}>{c}</li>)}</ul></div>
              </div>
            </div>
          )}
          {resultRegister && !resultRegister.error && (
            <div className="import-report" role="status">
              <h3>Результат</h3>
              <p>Принято: <strong>{resultRegister.accepted}</strong>, отклонено: <strong>{resultRegister.rejected}</strong></p>
              {resultRegister.errors?.length > 0 && <details><summary>Ошибки ({resultRegister.errors.length})</summary><ul>{resultRegister.errors.map((e, i) => <li key={i}>Строка {e.row}: {e.message}</li>)}</ul></details>}
            </div>
          )}
          {resultRegister?.error && <div className="import-error" role="alert">{resultRegister.error}</div>}
        </section>
      )}

      <section className="upload-section" aria-labelledby="contacts-heading">
        <h2 id="contacts-heading">Загрузка контактов</h2>
        <p>Помещения уже должны быть в реестре. Обязательны: <strong>cadastral_number</strong> и хотя бы один из <strong>phone</strong>, <strong>email</strong>, <strong>telegram_id</strong>.</p>
        <ul>{EXPECTED_COLUMNS_CONTACTS.map((c) => <li key={c}><code>{c}</code></li>)}</ul>
        <form onSubmit={handleSubmitContacts}>
          <label htmlFor="contacts-file">Файл контактов</label>
          <input id="contacts-file" type="file" accept=".csv,.xlsx,.xls" onChange={(e) => { setFileContacts(e.target.files?.[0] || null); setResultContacts(null); setStructureErrorContacts(null) }} disabled={!token} />
          <span className="help">{fileContacts ? fileContacts.name : 'Файл не выбран'}</span>
          <button type="submit" disabled={!fileContacts || loadingContacts}>{loadingContacts ? 'Загрузка…' : 'Загрузить контакты'}</button>
        </form>
        {structureErrorContacts && (
          <div className="structure-error" role="alert">
            <h3>Ошибка структуры</h3>
            <p>{structureErrorContacts.detail || 'Требуются кадастр и хотя бы один контактный столбец.'}</p>
            <div className="columns-compare">
              <div><strong>Обнаружены:</strong><ul>{structureErrorContacts.detected.map((c, i) => <li key={i}>{c || '(пусто)'}</li>)}</ul></div>
              <div><strong>Ожидаются:</strong><ul>{structureErrorContacts.expected.map((c, i) => <li key={i}>{c}</li>)}</ul></div>
            </div>
          </div>
        )}
        {resultContacts && !resultContacts.error && (
          <div className="import-report" role="status">
            <h3>Результат</h3>
            <p>Принято: <strong>{resultContacts.accepted}</strong>, отклонено: <strong>{resultContacts.rejected}</strong></p>
            {resultContacts.errors?.length > 0 && <details><summary>Ошибки ({resultContacts.errors.length})</summary><ul>{resultContacts.errors.map((e, i) => <li key={i}>Строка {e.row}: {e.message}</li>)}</ul></details>}
          </div>
        )}
        {resultContacts?.error && <div className="import-error" role="alert">{resultContacts.error}</div>}
      </section>

      <section className="upload-section" aria-labelledby="template-heading">
        <h2 id="template-heading">Шаблон контактов по подъезду</h2>
        <p>Скачайте XLSX со всеми помещениями выбранного подъезда и известными контактами. Заполните или отредактируйте и загрузите через «Загрузка контактов».</p>
        <form onSubmit={handleDownloadTemplate}>
          <label htmlFor="template-entrance">Подъезд</label>
          <select id="template-entrance" value={entrance} onChange={(e) => setEntrance(e.target.value)} disabled={!token} aria-describedby="template-entrance-help">
            <option value="">— выберите —</option>
            {entrances.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
          <span id="template-entrance-help" className="help">{entrances.length === 0 && token ? 'Нет подъездов в реестре' : ''}</span>
          <button type="submit" disabled={!entrance || loadingTemplate}>{loadingTemplate ? 'Формирование…' : 'Сформировать шаблон'}</button>
        </form>
        {templateError && <div className="import-error" role="alert">{templateError}</div>}
      </section>
    </div>
  )
}
