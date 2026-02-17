import { ReactNode } from 'react'

interface CardProps {
  title: string
  href: string
  icon?: ReactNode
  children: ReactNode
}

export function Card({ title, href, icon, children }: CardProps) {
  return (
    <a
      href={href}
      className="group block rounded-lg border border-gray-200 p-4 transition-colors hover:border-gray-300 hover:bg-gray-50 dark:border-neutral-800 dark:hover:border-neutral-700 dark:hover:bg-neutral-900"
    >
      <div className="flex items-center gap-2">
        {icon && <span className="text-2xl">{icon}</span>}
        <span className="font-semibold text-gray-900 dark:text-gray-100">
          {title} <span className="inline-block transition-transform group-hover:translate-x-1">→</span>
        </span>
      </div>
      <span className="mt-2 block text-sm text-gray-600 dark:text-gray-400">{children}</span>
    </a>
  )
}

interface CardsProps {
  children: ReactNode
}

export function Cards({ children }: CardsProps) {
  return (
    <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
      {children}
    </div>
  )
}
