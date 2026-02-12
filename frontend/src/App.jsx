import { useState, useEffect } from 'react'
import { Routes, Route, Link, useSearchParams, useNavigate } from 'react-router-dom'
import Upload from './pages/Upload'
import Premises from './pages/Premises'
import Form from './pages/Form'
import Login from './pages/Login'
import AuthCallback from './pages/AuthCallback'
import Policy from './pages/Policy'

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

function Home() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
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
  return <p>Фронтенд (React + Vite). Выберите помещение или загрузку реестра.</p>
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
      <h1>Кворум-МКД</h1>
      <nav>
        <Link to="/">Главная</Link>
        <Link to="/premises">Выбор помещения</Link>
        {token ? (
          <Link to="/upload">Загрузка реестра</Link>
        ) : (
          <Link to="/login">Войти через Telegram</Link>
        )}
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/premises" element={<Premises />} />
        <Route path="/form" element={<Form />} />
        <Route path="/login" element={<Login />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/policy" element={<Policy />} />
      </Routes>
    </div>
  )
}

export default App
