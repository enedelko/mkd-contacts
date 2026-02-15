/**
 * ADM-09: Проверка ответа админ-API на 403 "Policy consent required" и редирект на страницу согласия.
 * Использовать после каждого fetch к /api/admin/* или /api/superadmin/*.
 * При 403 читает body; при ином статусе body не потребляется.
 * @param {Response} res — ответ fetch
 * @param {function} navigate — navigate из useNavigate()
 * @returns {Promise<{ redirectConsent: boolean, dataFor403?: object }>}
 *   redirectConsent === true — выполнен редирект на /admin/consent, выйти.
 *   dataFor403 — при 403 с иной причиной (body уже прочитан), для отображения ошибки.
 */
export async function checkConsentRedirect(res, navigate) {
  if (res.status !== 403) return { redirectConsent: false }
  const data = await res.json().catch(() => ({}))
  if (data.detail === 'Policy consent required') {
    navigate('/admin/consent', { replace: true })
    return { redirectConsent: true }
  }
  return { redirectConsent: false, dataFor403: data }
}
