import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

// OPS-02: при 503 любой запрос к API — показываем заглушку (перехват в App по событию mkd-503)
const originalFetch = window.fetch
window.fetch = function (...args) {
  return originalFetch.apply(this, args).then((res) => {
    if (res.status === 503) {
      window.dispatchEvent(new CustomEvent('mkd-503'))
    }
    return res
  })
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
