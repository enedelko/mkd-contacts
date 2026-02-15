import { useState, useEffect } from 'react'
import { Routes, Route, Link, useSearchParams, useNavigate } from 'react-router-dom'
import Upload from './pages/Upload'
import Premises from './pages/Premises'
import Form from './pages/Form'
import Login from './pages/Login'
import AuthCallback from './pages/AuthCallback'
import Policy from './pages/Policy'
import AdminContacts from './pages/AdminContacts'
import AdminContactsList from './pages/AdminContactsList'
import AuditLog from './pages/AuditLog'
import ChangePassword from './pages/ChangePassword'
import SuperadminAdmins from './pages/SuperadminAdmins'
import AdminConsent from './pages/AdminConsent'
import EntrancePicker from './components/EntrancePicker'
import TelegramIcon from './components/TelegramIcon'

/** Проверить, не протух ли JWT (по полю exp в payload). */
function isTokenExpired(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return !payload.exp || payload.exp * 1000 < Date.now()
  } catch {
    return true
  }
}

/** Вернуть токен из localStorage; если протух — удалить и вернуть null. */
function getToken() {
  if (typeof window === 'undefined') return null
  const t = localStorage.getItem('mkd_access_token')
  if (t && isTokenExpired(t)) {
    localStorage.removeItem('mkd_access_token')
    return null
  }
  return t
}

/** Удалить токен и оповестить приложение (навбар, компоненты). */
export function clearAuth() {
  localStorage.removeItem('mkd_access_token')
  window.dispatchEvent(new CustomEvent('mkd-auth-change'))
}

/** Роль из JWT (для отображения пунктов только суперадмину). */
export function getRoleFromToken(t) {
  if (!t) return null
  try {
    const payload = JSON.parse(atob(t.split('.')[1]))
    return payload.role || null
  } catch {
    return null
  }
}

/** FE-06: Максимум ячеек в одной визуальной строке шахматки. */
const CHESSBOARD_ROW_LIMIT = 9

/** FE-06: цвета фона ячейки по позиции ОСС. */
const STATE_BG = {
  none: '#fff',
  registered: '#fff9c4',
  vote_for: '#c8e6c9',
  full: '#66bb6a',
}

function Home() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = getToken()

  // --- Кворум ---
  const [quorum, setQuorum] = useState(null)
  const [quorumLoading, setQuorumLoading] = useState(true)
  const [quorumError, setQuorumError] = useState(false)

  // --- Шахматка ---
  const [entrance, setEntrance] = useState(null)
  const [board, setBoard] = useState(null)
  const [boardLoading, setBoardLoading] = useState(false)
  const [boardError, setBoardError] = useState(false)

  // Редирект из popup Telegram
  useEffect(() => {
    if (!window.opener) return
    const fromQuery = searchParams.get('hash') && searchParams.get('id')
    if (fromQuery) {
      navigate(`/auth/callback?${searchParams.toString()}`, { replace: true })
      return
    }
    const hashPart = window.location.hash?.slice(1)
    if (!hashPart) return
    const hashParams = new URLSearchParams(hashPart)
    if (hashParams.get('hash') && hashParams.get('id')) {
      navigate(`/auth/callback?${hashParams.toString()}`, { replace: true })
      return
    }
    if (hashParams.get('tgAuthResult')) {
      navigate(`/auth/callback${window.location.hash}`, { replace: true })
    }
  }, [searchParams, navigate])

  // Загрузка кворума
  useEffect(() => {
    setQuorumLoading(true)
    setQuorumError(false)
    fetch('/api/buildings/default/quorum')
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('fetch failed'))))
      .then((data) => { setQuorum(data); setQuorumError(false) })
      .catch(() => { setQuorum(null); setQuorumError(true) })
      .finally(() => setQuorumLoading(false))
  }, [])

  // Загрузка шахматки при выборе подъезда
  useEffect(() => {
    if (!entrance) { setBoard(null); return }
    setBoardLoading(true)
    setBoardError(false)
    fetch(`/api/premises/chessboard?entrance=${encodeURIComponent(entrance)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('fetch'))))
      .then((data) => setBoard(data))
      .catch(() => { setBoard(null); setBoardError(true) })
      .finally(() => setBoardLoading(false))
  }, [entrance])

  // Клик по ячейке помещения
  const handleCellClick = (premise, floor, premisesType) => {
    const stateData = {
      premise: { premise_id: premise.premise_id, number: premise.premises_number },
      entrance,
      floor,
      type: premisesType,
      hasEntrances: true,
    }
    if (token) {
      navigate('/admin/contacts', { state: stateData })
    } else {
      navigate('/form', { state: stateData })
    }
  }

  return (
    <>
      {/* SR-FE06-001: Блок кворума вверху */}
      <section className="home-quorum" aria-label="Прогноз кворума">
        {quorumLoading && <p className="quorum-loading">Загрузка данных кворума…</p>}
        {quorumError && !quorumLoading && (
          <p className="quorum-error">Данные по кворуму пока недоступны.</p>
        )}
        {quorum && !quorumLoading && (
          <div className="quorum-block">
            <h2>Кворум ОСС</h2>
            <p className="quorum-stats">
              Площадь с голосами «ЗА»: <strong>{quorum.area_voted_for}</strong> м² из <strong>{quorum.total_area}</strong> м²
              {quorum.total_area > 0 && (
                <> ({(quorum.ratio * 100).toFixed(1)}%, порог 66,7%)</>
              )}
            </p>
            <div className="quorum-progress-wrap">
              <div
                className="quorum-progress"
                style={{ width: `${Math.min(100, quorum.ratio * 100)}%` }}
                role="progressbar"
                aria-valuenow={quorum.ratio * 100}
                aria-valuemin="0"
                aria-valuemax="100"
              />
            </div>
            <p className={`quorum-result ${quorum.quorum_reached ? 'quorum-reached' : ''}`}>
              {quorum.quorum_reached ? 'Кворум набирается (порог 2/3 достигнут)' : 'Кворум не набирается (порог 2/3 пока не достигнут)'}
            </p>
          </div>
        )}
      </section>

      {/* SR-FE06-002: Выбор подъезда */}
      <p>Выберите помещение, чтобы оставить контакты и выразить свою позицию по ОСС.</p>
      <EntrancePicker
        selected={entrance}
        onSelect={(ent) => setEntrance(ent)}
        onReset={() => setEntrance(null)}
        prompt="Выберите подъезд для просмотра помещений."
      />

      {/* SR-FE06-004: % площади ЗА над шахматкой */}
      {board && !boardLoading && (
        <div className="chessboard-entrance-stats">
          Площадь «ЗА» по подъезду: <strong>{board.entrance_area_voted_for}</strong> м² из <strong>{board.entrance_total_area}</strong> м²
          {board.entrance_total_area > 0 && (
            <> ({(board.entrance_ratio * 100).toFixed(1)}%)</>
          )}
        </div>
      )}

      {/* Шахматка */}
      {boardLoading && <p className="chessboard-loading">Загрузка помещений…</p>}
      {boardError && !boardLoading && <p className="chessboard-error">Не удалось загрузить данные. Попробуйте ещё раз.</p>}

      {board && !boardLoading && (
        <div className="chessboard" aria-label="Шахматка помещений">
          {board.floors.map((fl) => {
            const chunks = []
            for (let i = 0; i < fl.premises.length; i += CHESSBOARD_ROW_LIMIT) {
              chunks.push(fl.premises.slice(i, i + CHESSBOARD_ROW_LIMIT))
            }
            return (
              <div key={fl.floor} className="chessboard-floor">
                <div className="chessboard-floor-label">Этаж {fl.floor}</div>
                {chunks.map((chunk, ci) => (
                  <div key={ci} className="chessboard-row">
                    {chunk.map((p) => (
                      <button
                        key={p.premise_id}
                        type="button"
                        className={`chessboard-cell state-${p.contact_state}`}
                        style={{ background: STATE_BG[p.contact_state] || STATE_BG.none }}
                        onClick={() => handleCellClick(p, fl.floor, p.premises_type)}
                        title={`${p.premises_type} ${p.premises_number}`}
                      >
                        <span className="cell-type">{p.premises_type}</span>
                        <span className="cell-number">{p.premises_number}</span>
                        <span className="cell-icons">
                          {p.has_telegram_or_phone && <TelegramIcon width={14} height={14} />}
                          {p.has_email_only && <span className="cell-email" aria-label="Email">✉</span>}
                        </span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )
          })}
          {board.floors.length === 0 && <p className="chessboard-empty">В подъезде нет помещений.</p>}

          {/* Легенда */}
          <div className="chessboard-legend" aria-label="Обозначения">
            <span className="legend-title">Обозначения:</span>
            <span className="legend-item"><span className="legend-swatch" style={{ background: STATE_BG.none }} />Нет информации</span>
            <span className="legend-item"><span className="legend-swatch" style={{ background: STATE_BG.registered }} />Зарегистрированы в ЭД</span>
            <span className="legend-item"><span className="legend-swatch" style={{ background: STATE_BG.vote_for }} />Есть голос «ЗА»</span>
            <span className="legend-item"><span className="legend-swatch" style={{ background: STATE_BG.full }} />Все голосуют «ЗА»</span>
            <span className="legend-item"><TelegramIcon width={14} height={14} /> Есть Telegram / телефон</span>
            <span className="legend-item"><span className="cell-email">✉</span> Только email</span>
          </div>
        </div>
      )}
    </>
  )
}

function App() {
  const [token, setToken] = useState(getToken)
  useEffect(() => {
    const onAuthChange = () => setToken(getToken())
    window.addEventListener('mkd-auth-change', onAuthChange)
    // Проверять срок действия токена каждые 30 секунд
    const interval = setInterval(() => setToken(getToken()), 30_000)
    return () => {
      window.removeEventListener('mkd-auth-change', onAuthChange)
      clearInterval(interval)
    }
  }, [])
  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <h1>Кворум-МКД</h1>
          <nav>
            <Link to="/">Главная</Link>
            {token ? (
              <>
                <Link to="/admin/contacts">Контакт по помещению</Link>
                <Link to="/upload">Загрузка реестра</Link>
                <Link to="/admin/contacts/list">Контакты</Link>
                <Link to="/admin/audit">Аудит-лог</Link>
                {getRoleFromToken(token) === 'super_administrator' && (
                  <Link to="/admin/superadmin">Управление админами</Link>
                )}
                <Link to="/admin/change-password">Смена пароля</Link>
                <button type="button" className="nav-logout" onClick={() => { clearAuth(); setToken(null) }}>Выйти</button>
              </>
            ) : (
              <>
                <Link to="/premises">Контакт по помещению</Link>
                <Link to="/login">Вход для администраторов</Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <div className="app-body">
        <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/premises" element={<Premises />} />
        <Route path="/form" element={<Form />} />
        <Route path="/login" element={<Login />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/policy" element={<Policy />} />
        <Route path="/admin/contacts" element={<AdminContacts />} />
        <Route path="/admin/contacts/:id" element={<AdminContacts />} />
        <Route path="/admin/contacts/list" element={<AdminContactsList />} />
        <Route path="/admin/audit" element={<AuditLog />} />
        <Route path="/admin/consent" element={<AdminConsent />} />
        <Route path="/admin/change-password" element={<ChangePassword />} />
        <Route path="/admin/superadmin" element={<SuperadminAdmins />} />
        </Routes>
      </div>
    </div>
  )
}

export default App
