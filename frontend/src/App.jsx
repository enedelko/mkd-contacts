import { Routes, Route, Link } from 'react-router-dom'
import Upload from './pages/Upload'
import Premises from './pages/Premises'
import Form from './pages/Form'

function App() {
  return (
    <div className="app">
      <h1>Кворум-МКД</h1>
      <nav>
        <Link to="/">Главная</Link>
        <Link to="/premises">Выбор помещения</Link>
        <Link to="/upload">Загрузка реестра</Link>
      </nav>
      <Routes>
        <Route path="/" element={<p>Фронтенд (React + Vite). Выберите помещение или загрузку реестра.</p>} />
        <Route path="/premises" element={<Premises />} />
        <Route path="/form" element={<Form />} />
        <Route path="/upload" element={<Upload />} />
      </Routes>
    </div>
  )
}

export default App
