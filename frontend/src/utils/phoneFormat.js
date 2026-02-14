/**
 * Форматирование номера телефона при потере фокуса (onBlur).
 * Российские номера: +7 (XXX) XXX-XX-XX.
 */
export function formatPhoneOnBlur(value) {
  if (!value || typeof value !== 'string') return ''
  const trimmed = value.trim()
  if (!trimmed) return ''
  const digits = trimmed.replace(/\D/g, '')
  if (digits.length === 0) return ''
  let normalized = digits
  if (digits.startsWith('8') && digits.length === 11) {
    normalized = '7' + digits.slice(1)
  } else if (digits.length === 10) {
    normalized = '7' + digits
  }
  if (normalized.length === 11 && normalized.startsWith('7')) {
    return `+7 (${normalized.slice(1, 4)}) ${normalized.slice(4, 7)}-${normalized.slice(7, 9)}-${normalized.slice(9, 11)}`
  }
  return trimmed
}
