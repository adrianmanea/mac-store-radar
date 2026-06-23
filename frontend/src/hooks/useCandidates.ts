import { useCallback, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export interface Candidate {
  keyword: string
  source: string
  status: string // new | validated | watched | rejected
  best_opportunity: number | null
  n_apps: number | null
  reason: string | null
}

interface State {
  rows: Candidate[]
  loading: boolean
  error: string | null
  refresh: () => void
}

/** The discovery pool: scored candidates the operator can choose to track. */
export function useCandidates(): State {
  const [rows, setRows] = useState<Candidate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    const { data, error } = await supabase
      .from('niche_candidates')
      .select('keyword, source, status, best_opportunity, n_apps, reason')
      .in('status', ['validated', 'watched'])
      .order('best_opportunity', { ascending: false, nullsFirst: false })
    if (error) setError(error.message)
    else setRows((data ?? []) as Candidate[])
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { rows, loading, error, refresh: load }
}
