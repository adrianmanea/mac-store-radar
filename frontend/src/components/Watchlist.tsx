import { useMemo, useState } from 'react'
import type { NicheScoreRow, SortKey } from '../types'

const COLUMNS: { key: SortKey; label: string; estimate?: boolean }[] = [
  { key: 'opportunity', label: 'Opportunity' },
  { key: 'momentum', label: 'Momentum' },
  { key: 'demand', label: 'Demand', estimate: true },
  { key: 'competition', label: 'Competition' },
  { key: 'gap', label: 'Gap' },
  { key: 'monetization', label: 'Monetization' },
]

function num(v: number | null): string {
  return v == null ? '—' : v.toFixed(1)
}

function Liveness({ row }: { row: NicheScoreRow }) {
  const f = row.raw_inputs?.avg_freshness
  if (f == null) return <span className="text-zinc-500">—</span>
  const tone = f >= 0.66 ? 'text-emerald-300' : f >= 0.4 ? 'text-amber-300' : 'text-red-300'
  return (
    <span className={tone} title="Avg incumbent liveness (recency of last update)">
      {Math.round(f * 100)}%
    </span>
  )
}

function OpportunityBadge({ row }: { row: NicheScoreRow }) {
  if (row.gated_out)
    return (
      <span
        className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400"
        title={row.gate_reason ?? 'gated out'}
      >
        gated
      </span>
    )
  const v = row.opportunity ?? 0
  const tone =
    v >= 30
      ? 'bg-emerald-500/20 text-emerald-300'
      : v >= 10
        ? 'bg-amber-500/20 text-amber-300'
        : 'bg-zinc-700/40 text-zinc-300'
  return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${tone}`}>{v.toFixed(1)}</span>
}

interface Props {
  rows: NicheScoreRow[]
  loading: boolean
  error: string | null
}

export function Watchlist({ rows, loading, error }: Props) {
  const [sort, setSort] = useState<SortKey>('opportunity')
  const sorted = useMemo(
    () => [...rows].sort((a, b) => (b[sort] ?? -1) - (a[sort] ?? -1)),
    [rows, sort],
  )

  if (loading)
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded bg-zinc-900/60" />
        ))}
      </div>
    )
  if (error)
    return (
      <div className="rounded-lg border border-red-900/50 bg-red-950/40 p-4 text-sm text-red-300">
        {error}
      </div>
    )
  if (rows.length === 0)
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-8 text-center text-sm text-zinc-400">
        No tracked niches yet. Go to <span className="text-zinc-200">Discovery</span> and Track the
        candidates worth building.
      </div>
    )

  return (
    <div className="overflow-hidden rounded-lg border border-zinc-800">
      <table className="w-full text-sm">
        <thead className="bg-zinc-900 text-left text-xs uppercase tracking-wide text-zinc-400">
          <tr>
            <th className="px-4 py-3 font-medium">Niche</th>
            {COLUMNS.map((c) => (
              <th key={c.key} className="px-4 py-3 font-medium">
                <button
                  onClick={() => setSort(c.key)}
                  className={`inline-flex items-center gap-1 hover:text-zinc-100 ${
                    sort === c.key ? 'text-zinc-100' : ''
                  }`}
                >
                  {c.label}
                  {c.estimate && (
                    <span className="text-[10px] text-amber-400/80" title="Estimate">
                      est.
                    </span>
                  )}
                  {sort === c.key && <span aria-hidden>↓</span>}
                </button>
              </th>
            ))}
            <th className="px-4 py-3 font-medium" title="Avg incumbent liveness">
              Live
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800">
          {sorted.map((row) => (
            <tr key={row.niche_id} className="hover:bg-zinc-900/50">
              <td className="px-4 py-3 font-medium text-zinc-100">
                {row.niches?.display_name ?? row.niches?.keyword ?? `#${row.niche_id}`}
              </td>
              <td className="px-4 py-3">
                <OpportunityBadge row={row} />
              </td>
              <td className="px-4 py-3 text-zinc-300">{num(row.momentum)}</td>
              <td className="px-4 py-3 text-zinc-300">{num(row.demand)}</td>
              <td className="px-4 py-3 text-zinc-300">{num(row.competition)}</td>
              <td className="px-4 py-3 text-zinc-300">{num(row.gap)}</td>
              <td className="px-4 py-3 text-zinc-300">{num(row.monetization)}</td>
              <td className="px-4 py-3">
                <Liveness row={row} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
