/**
 * BOT-01: Просмотр нераспознанных вводов бота (только super_administrator).
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAuth } from '../App'
import { checkConsentRedirect } from '../utils/adminApi'

function getToken() {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('mkd_access_token')
}

const PAGE_SIZE = 50

export default function BotUnrecognized() {
  const navigate = useNavigate()
  const token = getToken()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async (off) => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/superadmin/bot-unrecognized?limit=${PAGE_SIZE}&offset=${off}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const { redirectConsent, dataFor403 } = await checkConsentRedirect(res, navigate)
      if (redirectConsent) return
      if (dataFor403 !== undefined || res.status === 401 || res.status === 403) {
        clearAuth()
        navigate('/login', { replace: true })
        return
      }
      const data = await res.json().catch(() => ({ items: [], total: 0 }))
      if (res.ok) {
        setItems(data.items || [])
        setTotal(data.total || 0)
      } else {
        setError(typeof data.detail === 'string' ? data.detail : 'Ошибка загрузки')
      }
    } catch (err) {
      setError(err.message || 'Ошибка сети')
    } finally {
      setLoading(false)
    }
  }, [token, navigate])

  useEffect(() => {
    if (!token) { navigate('/login', { replace: true }); return }
    fetchData(offset)
  }, [token, navigate, fetchData, offset])

  if (!token) return null

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div className="superadmin-admins-page">
      <h1>Нераспознанные вводы бота</h1>
      <p className="superadmin-admins-hint">
        Сообщения пользователей, которые бот не смог распознать. Проанализируйте частотные паттерны
        и добавьте недостающие синонимы на странице «Словарь бота».
      </p>
      {error && <p className="superadmin-admins-error">{error}</p>}

      {loading && <p>Загрузка…</p>}
      {!loading && items.length === 0 && <p className="superadmin-empty">Нет нераспознанных вводов.</p>}

      {!loading && items.length > 0 && (
        <>
          <p>Всего записей: {total}</p>
          <table className="superadmin-admins-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Ввод пользователя</th>
                <th>Дата</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r, i) => (
                <tr key={r.id}>
                  <td>{offset + i + 1}</td>
                  <td style={{ fontFamily: 'monospace' }}>{r.input_text}</td>
                  <td>{r.created_at ? new Date(r.created_at).toLocaleString('ru-RU') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="audit-pagination" style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                Назад
              </button>
              <span>Страница {currentPage} из {totalPages}</span>
              <button type="button" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
                Вперёд
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
