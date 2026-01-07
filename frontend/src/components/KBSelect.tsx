import { useState } from 'react'
import { ChevronDownIcon } from './Icons'

import { UI_CONFIG } from '../config/uiConfig'

interface KBSelectOption<T> {
  value: T
  label: string
}

interface KBSelectProps<T extends string | number> {
  label: string
  value: T
  onChange: (v: T) => void
  options: KBSelectOption<T>[]
  width?: number | string
  dropUp?: boolean
}

export function KBSelect<T extends string | number>({ 
  label, 
  value, 
  onChange, 
  options, 
  width = UI_CONFIG.selectWidth,
  dropUp = false
}: KBSelectProps<T>) {
  const [isOpen, setIsOpen] = useState(false)
  const currentLabel = options.find(o => o.value === value)?.label || String(value)

  return (
    <div 
      className="kb-select-container"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) {
          setIsOpen(false)
        }
      }}
    >
      {label && <div className="kb-select-label">{label}</div>}
      
      <div className="kb-select-wrapper" style={{ width }}>
        <div
          onClick={() => setIsOpen(!isOpen)}
          tabIndex={0}
          className="kb-select-trigger"
        >
          <span>{currentLabel}</span>
          <div className={`kb-select-icon ${isOpen ? 'rotated' : ''}`}>
            <ChevronDownIcon size={10} />
          </div>
        </div>

        {isOpen && (
          <div 
            className="kb-select-dropdown" 
            style={dropUp ? { top: 'auto', bottom: `calc(100% + ${UI_CONFIG.dropdownOffset}px)` } : { top: `calc(100% + ${UI_CONFIG.dropdownOffset}px)` }}
          >
            {options.map((opt) => (
              <div
                key={String(opt.value)}
                className={`kb-select-option ${value === opt.value ? 'active' : ''}`}
                onMouseDown={(e) => {
                  e.preventDefault()
                  onChange(opt.value)
                  setIsOpen(false)
                }}
              >
                {opt.label}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

