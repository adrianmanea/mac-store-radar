// Mirrors the niche_scores + niches tables (TECH-PRD §2).

export interface NicheScoreRow {
  niche_id: number
  captured_at: string
  demand: number | null
  competition: number | null
  gap: number | null
  monetization: number | null
  buildability: number | null
  opportunity: number | null
  momentum: number | null
  gated_out: boolean
  gate_reason: string | null
  raw_inputs: { avg_freshness?: number | null } | null
  niches: { keyword: string; display_name: string | null } | null
}

export type SortKey = 'opportunity' | 'momentum' | 'demand' | 'competition' | 'gap' | 'monetization'
