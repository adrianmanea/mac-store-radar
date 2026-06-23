import { useState } from 'react'
import { useCandidates } from '../hooks/useCandidates'
import { setWatch } from '../lib/watch'

// The discovery pool: every scored candidate. Operator hand-picks which to track via the
// Track button (routes through the watch Edge Function). Watched ones get an Untrack toggle.

export function Discovery() {
  const { rows, loading, error, refresh } = useCandidates()
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

  if (loading) return <div className="text-sm text-zinc-400">Loading candidate pool…</div>
  if (error)
    return (
      <div className="rounded-lg border border-red-900/50 bg-red-950/40 p-4 text-sm text-red-300">
        {error}
      </div>
    )
  if (rows.length === 0)
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-8 text-center text-sm text-zinc-400">
        No scored candidates yet. Discovery fills this pool — run{' '}
        <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-200">radar --discover</code>.
      </div>
    )

  const watchedCount = rows.filter((r) => r.status === 'watched').length

  return (
    <div>
      <p className="mb-3 text-sm text-zinc-400">
        {rows.length} scored candidates · {watchedCount} tracked. Pick the ones worth building.
      </p>
      {actionError && (
        <div className="mb-3 rounded border border-red-900/50 bg-red-950/40 p-2 text-xs text-red-300">
          {actionError}
        </div>
      )}
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
    </div>
  )
}
