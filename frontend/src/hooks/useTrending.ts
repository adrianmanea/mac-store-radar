import { useCallback, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export interface TrendingApp {
  app_id: number
  name: string
  category: string | null
  release_date: string | null
  current_ver_date: string | null
  ratings_per_day: number | null
}

export type TrendSort = 'velocity' | 'newest'

export interface TrendingQuery {
  page: number
  pageSize: number
  sort: TrendSort
  youngOnly: boolean
}

interface State {
  rows: TrendingApp[]
  total: number
  loading: boolean
  error: string | null
}

const YOUNG_CUTOFF_DAYS = 540 // ~18 months

export function useTrending(q: TrendingQuery): State {
  const [rows, setRows] = useState<TrendingApp[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    let query = supabase
      .from('apps')
      .select('app_id, name, category, release_date, current_ver_date, ratings_per_day', {
        count: 'exact',
      })

    if (q.sort === 'velocity') {
      query = query
        .not('ratings_per_day', 'is', null)
        .order('ratings_per_day', { ascending: false, nullsFirst: false })
    } else {
      query = query
        .not('release_date', 'is', null)
        .order('release_date', { ascending: false, nullsFirst: false })
    }

    if (q.youngOnly) {
      const cutoff = new Date(Date.now() - YOUNG_CUTOFF_DAYS * 86400_000).toISOString()
      query = query.gte('release_date', cutoff)
    }

    const from = q.page * q.pageSize
    const { data, error, count } = await query.range(from, from + q.pageSize - 1)
    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }
    setRows((data ?? []) as TrendingApp[])
    setTotal(count ?? 0)
    setLoading(false)
  }, [q.page, q.pageSize, q.sort, q.youngOnly])

  useEffect(() => {
    load()
  }, [load])

  return { rows, total, loading, error }
}
