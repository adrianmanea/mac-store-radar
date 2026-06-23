import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import type { NicheScoreRow } from '../types'

interface State {
  rows: NicheScoreRow[]
  loading: boolean
  error: string | null
}

/** Fetch the latest niche_scores row per niche (scores are themselves a time-series). */
export function useNicheScores(): State {
  const [state, setState] = useState<State>({ rows: [], loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const { data, error } = await supabase
        .from('niche_scores')
        .select(
          'niche_id, captured_at, demand, competition, gap, monetization, buildability, opportunity, momentum, gated_out, gate_reason, niches(keyword, display_name)',
        )
        .order('captured_at', { ascending: false })

      if (cancelled) return
      if (error) {
        setState({ rows: [], loading: false, error: error.message })
        return
      }

      // Keep only the most recent row per niche (rows arrive newest-first).
      const latest = new Map<number, NicheScoreRow>()
      for (const row of (data ?? []) as unknown as NicheScoreRow[]) {
        if (!latest.has(row.niche_id)) latest.set(row.niche_id, row)
      }
      setState({ rows: [...latest.values()], loading: false, error: null })
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
