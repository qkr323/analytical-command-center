'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV_LINKS = [
  { href: '/',             label: 'Dashboard'   },
  { href: '/positions',    label: 'Positions'   },
  { href: '/transactions', label: 'Transactions'},
  { href: '/history',      label: 'History'     },
  { href: '/pnl',          label: 'P&L'         },
  { href: '/currency',     label: 'Currency'    },
]

export default function NavBar() {
  const path = usePathname()
  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-screen-xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-1">
          <span className="font-semibold text-slate-800 text-lg mr-4">Portfolio Tracker</span>
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`px-3 py-1.5 rounded-md text-sm transition-colors
                ${path === href
                  ? 'bg-slate-100 text-slate-900 font-medium'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'}`}
            >
              {label}
            </Link>
          ))}
        </div>
        <span className="text-xs text-slate-400">HKD base currency</span>
      </div>
    </nav>
  )
}
