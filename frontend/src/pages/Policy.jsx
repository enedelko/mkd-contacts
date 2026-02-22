/**
 * Политика конфиденциальности — обработка ПДн в соответствии с 152-ФЗ.
 * Текст политики в frontend/src/content/policy.md, конвертируется в HTML при сборке.
 * Раздел 9: перечень админов (ФИО, помещение) подгружается с /api/policy/admins.
 */
import { useState, useEffect } from 'react'
import policyContent from '@/content/policy.md?policy'

export default function Policy() {
  const [admins, setAdmins] = useState([])
  const [adminsLoading, setAdminsLoading] = useState(true)
  const [adminsError, setAdminsError] = useState(false)

  useEffect(() => {
    let cancelled = false
    setAdminsLoading(true)
    setAdminsError(false)
    fetch('/api/policy/admins')
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('Failed to load'))))
      .then((data) => {
        if (!cancelled && Array.isArray(data)) setAdmins(data)
      })
      .catch(() => {
        if (!cancelled) setAdminsError(true)
      })
      .finally(() => {
        if (!cancelled) setAdminsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  return (
    <div className="policy-page">
      <div dangerouslySetInnerHTML={{ __html: policyContent.htmlBefore }} />
      {adminsLoading && <p className="policy-admins-loading">Загрузка списка администраторов…</p>}
      {adminsError && <p className="policy-admins-error">Список администраторов временно недоступен.</p>}
      {!adminsLoading && !adminsError && admins.length > 0 && (
        <div className="policy-admins-list">
          <p>Перечень администраторов Приложения (ФИО, помещение):</p>
          <ul>
            {admins.map((a, i) => (
              <li key={i}>{a.full_name} — {a.premises}</li>
            ))}
          </ul>
        </div>
      )}
      {policyContent.htmlAfter && (
        <div dangerouslySetInnerHTML={{ __html: policyContent.htmlAfter }} />
      )}
    </div>
  )
}
