export type Phase = 'detection' | 'evidence' | 'conclusion'

export type Strength = 'strong' | 'moderate' | 'weak' | 'contradictory'

export interface AgentEvent {
  type: 'phase_start' | 'query' | 'phase_complete' | 'complete' | 'error'
  phase: Phase
  at: string
  sql?: string | null
  tool?: string
  result?: InvestigationResult
  error?: string
}

export interface Segment {
  device_type: string
  region: string
  quality: string
  hour_range: [number, number] | null
  value: number
  baseline_value: number
}

export interface Detection {
  metric: string
  anomaly_day: string
  most_affected: Segment
  delta_percent: number
  other_segments_checked: string[]
}

export interface EvidenceItem {
  hypothesis: string
  supported: boolean
  strength: Strength
  observation: string
}

export interface Conclusion {
  root_cause: string
  recommendation: string
  unresolved_uncertainty: string
}

export interface InvestigationResult {
  question: string
  stats: { queries: number; model_calls: number; seconds: number }
  detection?: Detection
  evidence?: EvidenceItem[]
  confidence?: { score: number; band: string }
  conclusion?: Conclusion
  error?: string
  phase?: string
}

export interface InvestigationSummary {
  id: string
  question: string
  status: 'running' | 'complete' | 'failed'
  created_at: string
  result: InvestigationResult | null
}

export const PHASES: { key: Phase; label: string }[] = [
  { key: 'detection', label: 'Detect & localize anomaly' },
  { key: 'evidence', label: 'Gather & validate evidence' },
  { key: 'conclusion', label: 'Form conclusion' },
]
