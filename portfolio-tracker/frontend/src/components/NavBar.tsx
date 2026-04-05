import Link from 'next/link'

export default function NavBar() {
  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-screen-xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <span className="font-semibold text-slate-800 text-lg">Portfolio Tracker</span>
          <Link href="/" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">
            Dashboard
          </Link>
          <Link href="/positions" className="text-sm text-slate-600 hover:text-slate-900 transition-colors">
            Positions
          </Link>
        </div>
        <span className="text-xs text-slate-400">HKD base currency</span>
      </div>
    </nav>
  )
}
