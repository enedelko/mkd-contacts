import { Routes, Route, Link } from 'react-router-dom'
import Upload from './pages/Upload'

function App() {
  return (
    <div className="app">
      <h1>Кворум-МКД</h1>
      <nav>
        <Link to="/">Главная</Link>
        <Link to="/upload">Загрузка реестра</Link>
      </nav>
      <Routes>
        <Route path="/" element={<p>Фронтенд (React + Vite). BE-01 — статический бандл через Nginx.</p>} />
        <Route path="/upload" element={<Upload />} />
      </Routes>
    </div>
  )
}

export default App
