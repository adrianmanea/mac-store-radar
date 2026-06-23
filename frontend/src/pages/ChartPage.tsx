import { Scatter } from '../components/Scatter'
import { useNicheScores } from '../hooks/useNicheScores'

export function ChartPage() {
  const { rows, loading, error } = useNicheScores()

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Chart</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Opportunity × Momentum quadrant of your tracked niches.
        </p>
      </header>

      {loading ? (
        <div className="h-96 animate-pulse rounded-lg bg-zinc-900/60" />
      ) : error ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/40 p-4 text-sm text-red-300">
          {error}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-8 text-center text-sm text-zinc-400">
          No tracked niches yet. Track candidates in Discovery to plot them here.
        </div>
      ) : (
        <Scatter rows={rows} />
      )}
    </div>
  )
}
