import { useEffect, useState } from 'react'
import { useTrending, type TrendSort } from '../hooks/useTrending'

const PAGE_SIZE = 50

function ageLabel(iso: string | null): string {
  if (!iso) return '—'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400_000)
  if (days < 60) return `${days}d`
  if (days < 730) return `${Math.round(days / 30)}mo`
  return `${Math.round(days / 365)}yr`
}

export function TrendingPage() {
  const [sort, setSort] = useState<TrendSort>('newest')
  const [youngOnly, setYoungOnly] = useState(false)
  const [page, setPage] = useState(0)

  useEffect(() => setPage(0), [sort, youngOnly])

  const { rows, total, loading, error } = useTrending({
    page,
    pageSize: PAGE_SIZE,
    sort,
    youngOnly,
  })
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Trending</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Apps getting traffic now. Velocity = Δratings/day — meaningful once the daily cron
          has ≥2 days of snapshots; until then sort by Newest to see fresh entrants.
        </p>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex rounded-md border border-zinc-800 p-0.5 text-sm">
          {(['velocity', 'newest'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSort(s)}
              className={`rounded px-3 py-1 capitalize ${
                sort === s ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          <input
            type="checkbox"
            checked={youngOnly}
            onChange={(e) => setYoungOnly(e.target.checked)}
          />
          Young only (&lt;18mo)
        </label>
        <span className="ml-auto text-xs text-zinc-500">{total} apps</span>
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse rounded bg-zinc-900/60" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/40 p-4 text-sm text-red-300">
          {error}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-8 text-center text-sm text-zinc-400">
          No apps yet. The daily run ingests the top-free chart + computes velocity.
        </div>
      ) : (
        <>
          <div className="overflow-hidden rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-900 text-left text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="px-4 py-3 font-medium">App</th>
                  <th className="px-4 py-3 font-medium">Ratings/day</th>
                  <th className="px-4 py-3 font-medium">Age</th>
                  <th className="px-4 py-3 font-medium">Updated</th>
                  <th className="px-4 py-3 font-medium">Category</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {rows.map((r) => (
                  <tr key={r.app_id} className="hover:bg-zinc-900/50">
                    <td className="px-4 py-3 font-medium text-zinc-100">{r.name}</td>
                    <td className="px-4 py-3 text-zinc-300">
                      {r.ratings_per_day == null ? '—' : r.ratings_per_day.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-zinc-400">{ageLabel(r.release_date)}</td>
                    <td className="px-4 py-3 text-zinc-400">{ageLabel(r.current_ver_date)} ago</td>
                    <td className="px-4 py-3 text-zinc-500">{r.category ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-zinc-400">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page === 0}
                className="rounded border border-zinc-800 px-3 py-1 hover:bg-zinc-800 disabled:opacity-40"
              >
                ← Prev
              </button>
              <span>
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= totalPages - 1}
                className="rounded border border-zinc-800 px-3 py-1 hover:bg-zinc-800 disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
