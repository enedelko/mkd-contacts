/**
 * FE-05: sessionStorage-кеш данных формы для автозаполнения
 * между переходами по помещениям (SR-FE05-001, SR-FE05-002).
 */

const CACHE_KEY = 'mkd_form_cache'
const SUBMITTED_KEY = 'mkd_form_submitted'

const FIELDS = [
  'isOwner',
  'phone',
  'email',
  'telegramId',
  'barrierVote',
  'voteFormat',
  'registeredEd',
]

export function saveFormData(data) {
  try {
    const obj = {}
    for (const key of FIELDS) {
      if (data[key] !== undefined) obj[key] = data[key]
    }
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(obj))
  } catch { /* quota / private mode */ }
}

export function loadFormData() {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function clearFormData() {
  try {
    sessionStorage.removeItem(CACHE_KEY)
    sessionStorage.removeItem(SUBMITTED_KEY)
  } catch { /* ignore */ }
}

export function markSubmitted() {
  try {
    sessionStorage.setItem(SUBMITTED_KEY, '1')
  } catch { /* ignore */ }
}

export function wasSubmitted() {
  try {
    return sessionStorage.getItem(SUBMITTED_KEY) === '1'
  } catch {
    return false
  }
}
