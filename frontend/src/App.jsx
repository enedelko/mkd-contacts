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

function Home() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [quorum, setQuorum] = useState(null)
  const [quorumLoading, setQuorumLoading] = useState(true)
  const [quorumError, setQuorumError] = useState(false)

  useEffect(() => {
    // Редирект из popup: Telegram может вернуть на origin с параметрами в hash
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

  useEffect(() => {
    setQuorumLoading(true)
    setQuorumError(false)
    fetch('/api/buildings/default/quorum')
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('fetch failed'))))
      .then((data) => {
        setQuorum(data)
        setQuorumError(false)
      })
      .catch(() => {
        setQuorum(null)
        setQuorumError(true)
      })
      .finally(() => setQuorumLoading(false))
  }, [])

  return (
    <>
      <p>Выберите помещение, чтобы оставить контакты и выразить свою позицию по ОСС.</p>
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
