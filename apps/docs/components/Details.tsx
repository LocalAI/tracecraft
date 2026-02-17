'use client'

import { ReactNode, useState } from 'react'

interface DetailsProps {
  summary: string
  children: ReactNode
  open?: boolean
}

export function Details({ summary, children, open = false }: DetailsProps) {
  const [isOpen, setIsOpen] = useState(open)

  return (
    <details
      className="my-4 rounded-lg border border-gray-200 dark:border-neutral-800"
      open={isOpen}
      onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="cursor-pointer select-none px-4 py-3 font-medium text-gray-900 hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-neutral-900">
        {summary}
      </summary>
      <div className="border-t border-gray-200 px-4 py-3 dark:border-neutral-800">
        {children}
      </div>
    </details>
  )
}
