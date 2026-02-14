/**
 * FE-03: Каскадные фильтры помещений (SR-FE03-001..006).
 * Подъезд → Этаж → Тип → Номер. Пустые уровни пропускаются автоматически.
 * После выбора — переход к форме (FE-04).
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const API = '/api/premises'

export default function Premises() {
  const [hasEntrances, setHasEntrances] = useState(null) // null = loading
  const [entrances, setEntrances] = useState([])
  const [floors, setFloors] = useState([])
  const [types, setTypes] = useState([])
  const [premises, setPremises] = useState([])
  const [entrance, setEntrance] = useState('')
  const [floor, setFloor] = useState('')
  const [type, setType] = useState('')
  const [selectedPremise, setSelectedPremise] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  // Шаг 1: загрузить подъезды; если пусто — сразу загрузить этажи
  useEffect(() => {
    setLoading(true)
    fetch(`${API}/entrances`)
      .then((r) => r.json())
      .then((d) => {
        const list = d.entrances || []
        setEntrances(list)
        setHasEntrances(list.length > 0)
        if (list.length === 0) {
          // Подъездов нет — загружаем этажи без фильтра по подъезду
          return fetch(`${API}/floors`)
            .then((r) => r.json())
            .then((d) => setFloors(d.floors || []))
        }
      })
      .catch(() => {
        setEntrances([])
        setHasEntrances(false)
      })
      .finally(() => setLoading(false))
  }, [])

  // Шаг 2: при выборе подъезда — загрузить этажи
  useEffect(() => {
    if (hasEntrances === null || !hasEntrances) return // пропускаем, если подъездов нет
    if (!entrance) {
      setFloors([])
      setFloor('')
      setType('')
      setTypes([])
      setPremises([])
      setSelectedPremise(null)
      return
    }
    setLoading(true)
    fetch(`${API}/floors?entrance=${encodeURIComponent(entrance)}`)
      .then((r) => r.json())
      .then((d) => setFloors(d.floors || []))
      .catch(() => setFloors([]))
      .finally(() => setLoading(false))
    setFloor('')
    setType('')
    setTypes([])
    setPremises([])
    setSelectedPremise(null)
  }, [entrance, hasEntrances])

  // Шаг 3: при выборе этажа — загрузить типы
  useEffect(() => {
    if (!floor) {
      setTypes([])
      setType('')
      setPremises([])
      setSelectedPremise(null)
      return
    }
    setLoading(true)
    const params = new URLSearchParams({ floor })
    if (entrance) params.set('entrance', entrance)
    fetch(`${API}/types?${params}`)
      .then((r) => r.json())
      .then((d) => setTypes(d.types || []))
      .catch(() => setTypes([]))
      .finally(() => setLoading(false))
    setType('')
    setPremises([])
    setSelectedPremise(null)
  }, [floor, entrance])

  // Шаг 4: при выборе типа — загрузить номера
  useEffect(() => {
    if (!floor || !type) {
      setPremises([])
      setSelectedPremise(null)
      return
    }
    setLoading(true)
    const params = new URLSearchParams({ floor, type })
    if (entrance) params.set('entrance', entrance)
    fetch(`${API}/numbers?${params}`)
      .then((r) => r.json())
      .then((d) => setPremises(d.premises || []))
      .catch(() => setPremises([]))
      .finally(() => setLoading(false))
    setSelectedPremise(null)
  }, [floor, type, entrance])

  const handleGoToForm = () => {
    if (selectedPremise) {
      navigate('/form', { state: { premise: selectedPremise, entrance, floor, type, hasEntrances } })
    }
  }

  const isEmpty = hasEntrances !== null && entrances.length === 0 && floors.length === 0 && !loading

  return (
    <div className="premises-page">
      <h1>Выбор помещения</h1>
      {error && <p className="error">{error}</p>}
      {hasEntrances === null && <p>Загрузка…</p>}
      {isEmpty && <p className="empty-message">Данные по дому пока не загружены.</p>}
      {!isEmpty && hasEntrances !== null && (
        <>
          <div className="cascade-filters">
            {/* Подъезд — только если есть данные */}
            {hasEntrances && (
              <label>
                Подъезд
                <select value={entrance} onChange={(e) => setEntrance(e.target.value)} disabled={loading}>
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
                disabled={(hasEntrances && !entrance) || loading || floors.length === 0}
              >
                <option value="">— выберите —</option>
                {floors.map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </label>
            <label>
              Тип помещения
              <select value={type} onChange={(e) => setType(e.target.value)} disabled={!floor || loading}>
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
                disabled={!type || loading}
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
          {selectedPremise && (
            <div className="selected-premise">
              <p>Выбрано: {entrance ? `подъезд ${entrance}, ` : ''}этаж {floor}, {type} № {selectedPremise.number}</p>
              <button type="button" onClick={handleGoToForm}>Перейти к форме анкеты</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
