import React from 'react'

export const ChevronDownIcon = ({ size = 10, className = "" }: { size?: number, className?: string }) => (
  <svg 
    width={size} 
    height={(size * 6) / 10} 
    viewBox="0 0 10 6" 
    fill="none" 
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <path 
      d="M1 1L5 5L9 1" 
      stroke="currentColor" 
      strokeWidth="1.5" 
      strokeLinecap="round" 
      strokeLinejoin="round"
    />
  </svg>
)

