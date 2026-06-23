import { useState } from 'react'
import { Discovery } from './components/Discovery'
import { Scatter } from './components/Scatter'
import { Sidebar, type View } from './components/Sidebar'
import { Watchlist } from './components/Watchlist'
import { useNicheScores } from './hooks/useNicheScores'

const TITLES: Record<View, { title: string; sub: string }> = {
  discovery: { title: 'Discovery', sub: 'Auto-found niches, scored. Track the ones worth building.' },
  watchlist: { title: 'Watchlist', sub: 'Niches you track — deep daily snapshots, momentum, freshness.' },
  chart: { title: 'Chart', sub: 'Opportunity × Momentum quadrant of your tracked niches.' },
}

export default function App() {
  const [view, setView] = useState<View>('discovery')
  const { rows, loading, error } = useNicheScores()

  return (
    <div className="flex min-h-screen bg-zinc-950 text-zinc-100">
      <Sidebar view={view} setView={setView} />
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-5xl px-8 py-10">
          <header className="mb-8">
            <h1 className="text-2xl font-bold tracking-tight">{TITLES[view].title}</h1>
            <p className="mt-1 text-sm text-zinc-400">{TITLES[view].sub}</p>
          </header>

          {view === 'discovery' && <Discovery />}
          {view === 'watchlist' && <Watchlist rows={rows} loading={loading} error={error} />}
          {view === 'chart' && <Scatter rows={rows} />}
        </div>
      </main>
    </div>
  )
}
