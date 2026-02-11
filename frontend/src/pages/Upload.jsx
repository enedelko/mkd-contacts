/**
 * LOST-02: Страница загрузки реестров (SR-LOST02-001..006).
 * Инструкция, выбор файла (.csv, .xlsx, .xls), валидация структуры, отчёт.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAuth } from '../App'

const EXPECTED_COLUMNS = [
  'cadastral_number',
  'area',
  'entrance',
  'floor',
  'premises_type',
  'premises_number',
  'phone',
  'email',
  'telegram_id',
  'how_to_address',
]

export default function Upload() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [structureError, setStructureError] = useState(null)
  const navigate = useNavigate()

  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('mkd_access_token') : null

  const handleFileChange = (e) => {
    const f = e.target.files?.[0]
    setFile(f || null)
    setResult(null)
    setStructureError(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file || !token) {
      setResult({ error: token ? 'Выберите файл' : 'Требуется авторизация' })
      return
    }
    setLoading(true)
    setResult(null)
    setStructureError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
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
        if (res.status === 400 && data.detail === 'Column structure mismatch' && data.expected_columns && data.detected_columns) {
          setStructureError({
            expected: data.expected_columns,
            detected: data.detected_columns,
          })
        } else {
          let errorMsg = `Ошибка ${res.status}`
          if (typeof data.detail === 'string') {
            errorMsg = data.detail
          } else if (Array.isArray(data.detail)) {
            errorMsg = data.detail.map((e) => e.msg || JSON.stringify(e)).join('; ')
          } else if (data.detail) {
            errorMsg = JSON.stringify(data.detail)
          }
          setResult({ error: errorMsg })
        }
        return
      }
      setResult(data)
    } catch (err) {
      setResult({ error: err.message || 'Ошибка сети' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="upload-page">
      <h1>Загрузка реестра</h1>

      {/* SR-LOST02-001: инструкция по форматам и колонкам */}
      <section className="instruction" aria-label="Инструкция">
        <h2>Инструкция</h2>
        <p>Поддерживаемые форматы: <strong>.csv</strong> (UTF-8, разделитель — точка с запятой), <strong>.xlsx</strong>, <strong>.xls</strong>.</p>
        <p>Ожидаемые колонки (обязательна <strong>кадастровый номер</strong>; для контакта — хотя бы одно из: телефон, email, telegram_id):</p>
        <ul>
          {EXPECTED_COLUMNS.map((c) => (
            <li key={c}><code>{c}</code></li>
          ))}
        </ul>
        <p>Одна строка файла = одно помещение + один контакт. Несколько контактов на одно помещение — несколько строк.</p>
      </section>

      {/* SR-LOST02-002, SR-LOST02-003: выбор файла с ПК и мобильных */}
      <form onSubmit={handleSubmit}>
        <label htmlFor="register-file">
          Выберите файл (.csv, .xlsx, .xls)
        </label>
        <input
          id="register-file"
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileChange}
          disabled={!token}
          aria-describedby="file-help"
        />
        <span id="file-help" className="help">{file ? file.name : 'Файл не выбран'}</span>
        <button type="submit" disabled={!file || loading}>
          {loading ? 'Загрузка…' : 'Загрузить реестр'}
        </button>
      </form>

      {/* SR-LOST02-004, SR-LOST02-005, SR-LOST02-006: ошибка структуры — сравнение колонок */}
      {structureError && (
        <div className="structure-error" role="alert">
          <h3>Ошибка структуры файла</h3>
          <p>Набор колонок не совпадает с ожидаемым. Импорт не выполнен.</p>
          <div className="columns-compare">
            <div>
              <strong>Обнаруженные колонки:</strong>
              <ul>{structureError.detected.map((c, i) => <li key={i}>{c || '(пусто)'}</li>)}</ul>
            </div>
            <div>
              <strong>Ожидаемые колонки:</strong>
              <ul>{structureError.expected.map((c, i) => <li key={i}>{c}</li>)}</ul>
            </div>
          </div>
        </div>
      )}

      {/* Отчёт об импорте */}
      {result && !result.error && (
        <div className="import-report" role="status">
          <h3>Результат импорта</h3>
          <p>Принято строк: <strong>{result.accepted}</strong></p>
          <p>Отклонено: <strong>{result.rejected}</strong></p>
          {result.errors?.length > 0 && (
            <details>
              <summary>Ошибки по строкам ({result.errors.length})</summary>
              <ul>
                {result.errors.map((e, i) => (
                  <li key={i}>Строка {e.row}: {e.message}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {result?.error && (
        <div className="import-error" role="alert">
          {result.error}
        </div>
      )}
    </div>
  )
}
