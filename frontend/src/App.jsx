import { useState, useEffect } from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import Upload from './pages/Upload'
import Premises from './pages/Premises'
import Form from './pages/Form'
import Login from './pages/Login'
import AuthCallback from './pages/AuthCallback'

const getToken = () => (typeof window !== 'undefined' ? localStorage.getItem('mkd_access_token') : null)

function App() {
  const [token, setToken] = useState(getToken)
  useEffect(() => {
    const onAuthChange = () => setToken(getToken())
    window.addEventListener('mkd-auth-change', onAuthChange)
    return () => window.removeEventListener('mkd-auth-change', onAuthChange)
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
        <Route path="/" element={<p>Фронтенд (React + Vite). Выберите помещение или загрузку реестра.</p>} />
        <Route path="/premises" element={<Premises />} />
        <Route path="/form" element={<Form />} />
        <Route path="/login" element={<Login />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/upload" element={<Upload />} />
      </Routes>
    </div>
  )
}

export default App
