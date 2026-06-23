import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/discovery', label: 'Discovery', icon: '🧭', hint: 'Scored candidate pool' },
  { to: '/trending', label: 'Trending', icon: '📈', hint: 'Apps getting traffic now' },
  { to: '/watchlist', label: 'Watchlist', icon: '★', hint: 'Niches you track' },
  { to: '/chart', label: 'Chart', icon: '◳', hint: 'Opportunity × Momentum' },
]

export function Sidebar() {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-8 px-2">
        <div className="text-sm font-bold tracking-tight text-zinc-100">Mac App Radar</div>
        <div className="mt-0.5 text-[11px] text-zinc-500">opportunity finder</div>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            title={n.hint}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                isActive
                  ? 'bg-zinc-800 text-zinc-100'
                  : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200'
              }`
            }
          >
            <span className="w-4 text-center">{n.icon}</span>
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto px-2 text-[11px] leading-relaxed text-zinc-600">
        Demand is an estimate (autocomplete + aggregate ratings), not measured search volume.
      </div>
    </aside>
  )
}
