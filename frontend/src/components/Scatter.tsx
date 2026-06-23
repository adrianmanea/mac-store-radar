import type { NicheScoreRow } from '../types'

// Opportunity × Momentum quadrant map (PRD §4). Pure SVG — no chart-lib dependency.
// X = momentum (0–100), Y = opportunity (auto-scaled to the data). Niches without a
// momentum value yet (< 2 snapshots) are listed below the plot, not dropped silently.

const W = 720
const H = 460
const PAD = 48

export function Scatter({ rows }: { rows: NicheScoreRow[] }) {
  const plotted = rows.filter((r) => r.momentum != null && !r.gated_out)
  const noMomentum = rows.filter((r) => r.momentum == null && !r.gated_out)

  const maxOpp = Math.max(10, ...plotted.map((r) => r.opportunity ?? 0))
  const x = (m: number) => PAD + (m / 100) * (W - 2 * PAD)
  const y = (o: number) => H - PAD - (o / maxOpp) * (H - 2 * PAD)

  const midX = x(50)
  const midOppY = y(maxOpp / 2)

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Opportunity by momentum scatter">
        {/* quadrant guides */}
        <line x1={midX} y1={PAD} x2={midX} y2={H - PAD} stroke="#3f3f46" strokeDasharray="4 4" />
        <line x1={PAD} y1={midOppY} x2={W - PAD} y2={midOppY} stroke="#3f3f46" strokeDasharray="4 4" />

        {/* axes */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="#52525b" />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="#52525b" />

        {/* axis labels */}
        <text x={W / 2} y={H - 12} textAnchor="middle" className="fill-zinc-400 text-[13px]">
          Momentum →
        </text>
        <text x={16} y={H / 2} textAnchor="middle" transform={`rotate(-90 16 ${H / 2})`} className="fill-zinc-400 text-[13px]">
          Opportunity →
        </text>

        {/* quadrant hints */}
        <text x={W - PAD - 6} y={PAD + 14} textAnchor="end" className="fill-emerald-500/60 text-[11px]">
          act now
        </text>
        <text x={PAD + 6} y={PAD + 14} className="fill-amber-400/60 text-[11px]">
          stable cash cow
        </text>

        {/* points */}
        {plotted.map((r) => (
          <g key={r.niche_id}>
            <circle cx={x(r.momentum!)} cy={y(r.opportunity ?? 0)} r={6} className="fill-emerald-400/80" />
            <text x={x(r.momentum!) + 9} y={y(r.opportunity ?? 0) + 4} className="fill-zinc-300 text-[11px]">
              {r.niches?.keyword ?? `#${r.niche_id}`}
            </text>
          </g>
        ))}
      </svg>

      {noMomentum.length > 0 && (
        <p className="mt-2 text-xs text-zinc-500">
          No momentum yet (need ≥2 daily snapshots): {noMomentum.map((r) => r.niches?.keyword).join(', ')}
        </p>
      )}
    </div>
  )
}
