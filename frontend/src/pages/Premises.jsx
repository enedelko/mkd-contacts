/**
 * FE-03: Каскадные фильтры помещений (SR-FE03-001..006).
 * Подъезд → Этаж → Тип → Номер. После выбора — переход к форме (FE-04).
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const API = '/api/premises'

export default function Premises() {
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

  useEffect(() => {
    fetch(`${API}/entrances`)
      .then((r) => r.json())
      .then((d) => setEntrances(d.entrances || []))
      .catch(() => setEntrances([]))
  }, [])

  useEffect(() => {
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
  }, [entrance])

  useEffect(() => {
    if (!entrance || !floor) {
      setTypes([])
      setType('')
      setPremises([])
      setSelectedPremise(null)
      return
    }
    setLoading(true)
    fetch(`${API}/types?entrance=${encodeURIComponent(entrance)}&floor=${encodeURIComponent(floor)}`)
      .then((r) => r.json())
      .then((d) => setTypes(d.types || []))
      .catch(() => setTypes([]))
      .finally(() => setLoading(false))
    setType('')
    setPremises([])
    setSelectedPremise(null)
  }, [entrance, floor])

  useEffect(() => {
    if (!entrance || !floor || !type) {
      setPremises([])
      setSelectedPremise(null)
      return
    }
    setLoading(true)
    fetch(`${API}/numbers?entrance=${encodeURIComponent(entrance)}&floor=${encodeURIComponent(floor)}&type=${encodeURIComponent(type)}`)
      .then((r) => r.json())
      .then((d) => setPremises(d.premises || []))
      .catch(() => setPremises([]))
      .finally(() => setLoading(false))
    setSelectedPremise(null)
  }, [entrance, floor, type])

  const handleSelectPremise = (p) => {
    setSelectedPremise(p)
  }

  const handleGoToForm = () => {
    if (selectedPremise) {
      navigate('/form', { state: { premise: selectedPremise, entrance, floor, type } })
    }
  }

  const isEmpty = entrances.length === 0 && !loading
  return (
    <div className="premises-page">
      <h1>Выбор помещения</h1>
      {error && <p className="error">{error}</p>}
      {isEmpty && <p className="empty-message">Данные по дому пока не загружены.</p>}
      {!isEmpty && (
        <>
          <div className="cascade-filters">
            <label>
              Подъезд
              <select value={entrance} onChange={(e) => setEntrance(e.target.value)} disabled={loading}>
                <option value="">— выберите —</option>
                {entrances.map((e) => (
                  <option key={e} value={e}>{e}</option>
                ))}
              </select>
            </label>
            <label>
              Этаж
              <select value={floor} onChange={(e) => setFloor(e.target.value)} disabled={!entrance || loading}>
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
              <p>Выбрано: подъезд {entrance}, этаж {floor}, {type} № {selectedPremise.number}</p>
              <button type="button" onClick={handleGoToForm}>Перейти к форме анкеты</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
