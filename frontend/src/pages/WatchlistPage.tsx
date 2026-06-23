import { useMemo, useState } from 'react'
import { Watchlist } from '../components/Watchlist'
import { useNicheScores } from '../hooks/useNicheScores'

export function WatchlistPage() {
  const { rows, loading, error } = useNicheScores()
  const [q, setQ] = useState('')
  const [minOpp, setMinOpp] = useState(0)
  const [hideGated, setHideGated] = useState(false)

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return rows.filter((r) => {
      const kw = (r.niches?.keyword ?? '').toLowerCase()
      if (needle && !kw.includes(needle)) return false
      if ((r.opportunity ?? 0) < minOpp) return false
      if (hideGated && r.gated_out) return false
      return true
    })
  }, [rows, q, minOpp, hideGated])

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Watchlist</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Niches you track — deep daily snapshots, momentum, freshness. {rows.length} tracked.
        </p>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter niche…"
          className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-zinc-600 focus:outline-none"
        />
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          Min opp
          <input
            type="number"
            min={0}
            value={minOpp}
            onChange={(e) => setMinOpp(Number(e.target.value) || 0)}
            className="w-16 rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-100 focus:border-zinc-600 focus:outline-none"
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          <input
            type="checkbox"
            checked={hideGated}
            onChange={(e) => setHideGated(e.target.checked)}
          />
          Hide gated
        </label>
        {!loading && (
          <span className="ml-auto text-xs text-zinc-500">{filtered.length} shown</span>
        )}
      </div>

      <Watchlist rows={filtered} loading={loading} error={error} />
    </div>
  )
}
