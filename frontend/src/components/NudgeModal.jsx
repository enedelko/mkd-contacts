/**
 * FE-05: Nudge-модал после успешной отправки анкеты (SR-FE05-003..005).
 * Предлагает указать данные по другому помещению.
 */
import { useEffect, useRef } from 'react'

export default function NudgeModal({ visible, onMap, onList, onClose }) {
  const dialogRef = useRef(null)

  useEffect(() => {
    if (visible) dialogRef.current?.focus()
  }, [visible])

  if (!visible) return null

  return (
    <div className="nudge-overlay" onClick={onClose}>
      <div
        className="nudge-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Заполнить данные по другому помещению"
        ref={dialogRef}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="nudge-title">Данные приняты!</h2>
        <p className="nudge-text">
          Если у вас есть другие помещения (машиноместо, кладовка)&nbsp;—
          вы можете заполнить анкету и по ним. Введённые данные подставятся автоматически.
        </p>
        <div className="nudge-actions">
          <button type="button" className="nudge-btn nudge-btn-primary" onClick={onMap}>
            Найти на карте
          </button>
          <button type="button" className="nudge-btn nudge-btn-secondary" onClick={onList}>
            Выбрать из списка
          </button>
          <button type="button" className="nudge-btn nudge-btn-close" onClick={onClose}>
            Это всё
          </button>
        </div>
      </div>
    </div>
  )
}
