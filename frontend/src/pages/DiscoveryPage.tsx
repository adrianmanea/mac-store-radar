import { useEffect, useState } from 'react'
import { useCandidates } from '../hooks/useCandidates'
import { setWatch } from '../lib/watch'

const PAGE_SIZE = 50

export function DiscoveryPage() {
  // filter inputs
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('') // debounced
  const [minOpp, setMinOpp] = useState(0)
  const [hideTracked, setHideTracked] = useState(false)
  const [page, setPage] = useState(0)

  // debounce the search box (avoid a query per keystroke)
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 300)
    return () => clearTimeout(t)
  }, [searchInput])

  // any filter change resets to the first page
  useEffect(() => setPage(0), [search, minOpp, hideTracked])

  const { rows, total, watchedTotal, loading, error, refresh } = useCandidates({
    page,
    pageSize: PAGE_SIZE,
    search,
    minOpp,
    hideTracked,
  })

  const [busy, setBusy] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  async function toggle(keyword: string, watched: boolean) {
    setBusy(keyword)
    setActionError(null)
    try {
      await setWatch(keyword, watched ? 'remove' : 'add')
      await refresh()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Discovery</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Auto-found niches, scored. {total} match · {watchedTotal} tracked. Track the ones worth
          building.
        </p>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Filter keyword…"
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
            checked={hideTracked}
            onChange={(e) => setHideTracked(e.target.checked)}
          />
          Hide tracked
        </label>
      </div>

      {actionError && (
        <div className="mb-3 rounded border border-red-900/50 bg-red-950/40 p-2 text-xs text-red-300">
          {actionError}
        </div>
      )}

      {loading ? (
        <Skeleton />
      ) : error ? (
        <ErrorBox msg={error} />
      ) : rows.length === 0 ? (
        <Empty filtered={total === 0 && (!!search || minOpp > 0)} />
      ) : (
        <>
          <div className="overflow-hidden rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-900 text-left text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="px-4 py-3 font-medium">Candidate</th>
                  <th className="px-4 py-3 font-medium">Opportunity</th>
                  <th className="px-4 py-3 font-medium">Apps</th>
                  <th className="px-4 py-3 font-medium">Source</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {rows.map((r) => {
                  const watched = r.status === 'watched'
                  return (
                    <tr key={r.keyword} className="hover:bg-zinc-900/50">
                      <td className="px-4 py-3 font-medium text-zinc-100">{r.keyword}</td>
                      <td className="px-4 py-3 text-zinc-300">
                        {r.best_opportunity == null ? '—' : r.best_opportunity.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-zinc-400">{r.n_apps ?? '—'}</td>
                      <td className="px-4 py-3 text-zinc-500">{r.source}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => toggle(r.keyword, watched)}
                          disabled={busy === r.keyword}
                          className={`rounded px-3 py-1 text-xs font-medium disabled:opacity-50 ${
                            watched
                              ? 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                              : 'bg-emerald-600/80 text-white hover:bg-emerald-600'
                          }`}
                        >
                          {busy === r.keyword ? '…' : watched ? 'Tracking ✓' : 'Track'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <Pager page={page} totalPages={totalPages} onPage={setPage} />
        </>
      )}
    </div>
  )
}

function Pager({
  page,
  totalPages,
  onPage,
}: {
  page: number
  totalPages: number
  onPage: (p: number) => void
}) {
  if (totalPages <= 1) return null
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-zinc-400">
      <button
        onClick={() => onPage(page - 1)}
        disabled={page === 0}
        className="rounded border border-zinc-800 px-3 py-1 hover:bg-zinc-800 disabled:opacity-40"
      >
        ← Prev
      </button>
      <span>
        Page {page + 1} of {totalPages}
      </span>
      <button
        onClick={() => onPage(page + 1)}
        disabled={page >= totalPages - 1}
        className="rounded border border-zinc-800 px-3 py-1 hover:bg-zinc-800 disabled:opacity-40"
      >
        Next →
      </button>
    </div>
  )
}

function Skeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="h-12 animate-pulse rounded bg-zinc-900/60" />
      ))}
    </div>
  )
}

function ErrorBox({ msg }: { msg: string }) {
  return (
    <div className="rounded-lg border border-red-900/50 bg-red-950/40 p-4 text-sm text-red-300">
      {msg}
    </div>
  )
}

function Empty({ filtered }: { filtered: boolean }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-8 text-center text-sm text-zinc-400">
      {filtered ? (
        'No candidates match the filters.'
      ) : (
        <>
          No scored candidates yet. Run{' '}
          <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-200">radar --discover</code>.
        </>
      )}
    </div>
  )
}
