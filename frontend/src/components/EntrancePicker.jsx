/**
 * UI-01: Переиспользуемый компонент выбора подъезда (SR-UI01-001..008).
 *
 * Props:
 *   selected       — текущий подъезд (string) или null
 *   onSelect       — callback при выборе подъезда
 *   onReset        — callback при «Выбрать другой подъезд»
 *   prompt         — текст подсказки (по умолчанию «Выберите подъезд»)
 *   emptyMessage   — текст при отсутствии данных
 *   barExtra       — доп. элементы справа в баре (ReactNode)
 *   authHeaders    — объект заголовков для запроса (опционально)
 */
import { useState, useEffect } from 'react'
import { entranceButtonLabel, entranceBarLabel } from '../utils/entranceLabel'

export default function EntrancePicker({
  selected = null,
  onSelect,
  onReset,
  prompt = 'Выберите подъезд.',
  emptyMessage = 'Данные по дому пока не загружены.',
  barExtra = null,
  authHeaders = null,
}) {
  const [entrances, setEntrances] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(false)
    const headers = authHeaders || {}
    fetch('/api/premises/entrances', { headers })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('fetch'))))
      .then((d) => setEntrances(d.entrances || []))
      .catch(() => { setEntrances([]); setError(true) })
      .finally(() => setLoading(false))
  }, [authHeaders])

  if (loading) {
    return <p className="entrance-loading">Загрузка подъездов…</p>
  }

  if (error) {
    return <p className="entrance-error">Не удалось загрузить подъезды.</p>
  }

  if (entrances.length === 0) {
    return <p className="entrance-empty">{emptyMessage}</p>
  }

  if (!selected) {
    return (
      <div className="entrance-picker">
        <p className="entrance-prompt">{prompt}</p>
        <div className="entrance-buttons" role="group" aria-label="Выбор подъезда">
          {entrances.map((ent) => (
            <button
              key={ent}
              type="button"
              className="entrance-btn"
              onClick={() => onSelect(ent)}
            >
              {entranceButtonLabel(ent)}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="entrance-bar">
      <span className="entrance-current">{entranceBarLabel(selected)}</span>
      <button type="button" className="btn-link" onClick={onReset}>
        Выбрать другой подъезд
      </button>
      {barExtra}
    </div>
  )
}
