/**
 * Текст для кнопок и опций выбора подъезда:
 * если название длиннее 5 символов — только название, иначе «Подъезд N».
 */
export function entranceButtonLabel(ent) {
  const s = String(ent ?? '').trim()
  return s.length > 5 ? s : `Подъезд ${s}`
}

/**
 * Текст для строки текущего выбора (бар): «Подъезд: N» или только название.
 */
export function entranceBarLabel(ent) {
  const s = String(ent ?? '').trim()
  return s.length > 5 ? s : `Подъезд: ${s}`
}

/**
 * Текст в предложении (нижний регистр): «подъезд N» или только название.
 */
export function entranceInlineLabel(ent) {
  const s = String(ent ?? '').trim()
  return s.length > 5 ? s : `подъезд ${s}`
}
