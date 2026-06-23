import { useCallback, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export interface Candidate {
  keyword: string
  source: string
  status: string // validated | watched
  best_opportunity: number | null
  n_apps: number | null
  reason: string | null
}

export interface CandidateQuery {
  page: number
  pageSize: number
  search: string
  minOpp: number
  hideTracked: boolean
}

interface State {
  rows: Candidate[]
  total: number // total matching the filters (across all pages)
  watchedTotal: number
  loading: boolean
  error: string | null
  refresh: () => void
}

/** Server-side paginated + filtered discovery pool (scales past the 1000-row cap). */
export function useCandidates(q: CandidateQuery): State {
  const [rows, setRows] = useState<Candidate[]>([])
  const [total, setTotal] = useState(0)
  const [watchedTotal, setWatchedTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    let query = supabase
      .from('niche_candidates')
      .select('keyword, source, status, best_opportunity, n_apps, reason', { count: 'exact' })
      .order('best_opportunity', { ascending: false, nullsFirst: false })

    query = q.hideTracked
      ? query.eq('status', 'validated')
      : query.in('status', ['validated', 'watched'])
    if (q.search.trim()) query = query.ilike('keyword', `%${q.search.trim()}%`)
    if (q.minOpp > 0) query = query.gte('best_opportunity', q.minOpp)

    const from = q.page * q.pageSize
    query = query.range(from, from + q.pageSize - 1)

    const { data, error, count } = await query
    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }
    setRows((data ?? []) as Candidate[])
    setTotal(count ?? 0)
    setLoading(false)
  }, [q.page, q.pageSize, q.search, q.minOpp, q.hideTracked])

  useEffect(() => {
    load()
  }, [load])

  // separate cheap count of tracked niches for the header
  useEffect(() => {
    supabase
      .from('niche_candidates')
      .select('keyword', { count: 'exact', head: true })
      .eq('status', 'watched')
      .then(({ count }) => setWatchedTotal(count ?? 0))
  }, [rows])

  return { rows, total, watchedTotal, loading, error, refresh: load }
}
