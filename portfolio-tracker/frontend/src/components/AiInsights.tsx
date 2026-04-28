'use client'

import { useCallback, useEffect, useState } from 'react'
import { PortfolioSummary } from '@/types/portfolio'

interface AnalysisResult {
  overall_assessment: string
  alignment_score: number
  top_risks: string[]
  trade_ideas: Array<{ action: string; instrument: string; rationale: string }>
  market_context: string
}

interface Props {
  portfolio: PortfolioSummary | null
}

const BADGE_COLORS: Record<string, { bg: string; text: string }> = {
  BUY: { bg: 'bg-emerald-100', text: 'text-emerald-700' },
  SELL: { bg: 'bg-red-100', text: 'text-red-700' },
  HOLD: { bg: 'bg-slate-100', text: 'text-slate-700' },
  REBALANCE: { bg: 'bg-amber-100', text: 'text-amber-700' },
}

function formatMinutesAgo(date: Date): string {
  const minutes = Math.floor((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes === 1) return '1 minute ago'
  if (minutes < 60) return `${minutes} minutes ago`
  const hours = Math.floor(minutes / 60)
  if (hours === 1) return '1 hour ago'
  if (hours < 24) return `${hours} hours ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days > 1 ? 's' : ''} ago`
}

export default function AiInsights({ portfolio }: Props) {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [analyzedAt, setAnalyzedAt] = useState<Date | null>(null)
  const [targetAlloc, setTargetAlloc] = useState<Record<string, number> | null>(null)

  // Load target allocation from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('retirement_target_alloc')
      if (stored) {
        try {
          setTargetAlloc(JSON.parse(stored))
        } catch (e) {
          setTargetAlloc(null)
        }
      }
    }
  }, [])

  const analyze = useCallback(async () => {
    if (!portfolio) return

    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/ai-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolio, targetAlloc }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.error || 'Analysis failed')
      }

      const data = await res.json()
      setAnalysis(data.analysis)
      setAnalyzedAt(new Date(data.analyzedAt))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [portfolio, targetAlloc])

  if (!portfolio) return null

  const scoreWidth = analysis ? Math.min(analysis.alignment_score * 10, 100) : 0

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">🤖 AI Portfolio Analysis</h2>
          <p className="text-xs text-slate-500 mt-1">
            Powered by Groq + Tavily {analyzedAt && `• Analyzed ${formatMinutesAgo(analyzedAt)}`}
          </p>
        </div>
        <button
          onClick={analyze}
          disabled={loading}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading ? 'Analyzing...' : 'Analyze Now'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm mb-4">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="text-slate-400 text-sm">
            <div className="animate-spin inline-block w-4 h-4 border-2 border-slate-300 border-t-slate-600 rounded-full mr-2" />
            Analyzing portfolio...
          </div>
        </div>
      )}

      {analysis && (
        <div className="space-y-6">
          {/* Overall Assessment */}
          <div>
            <h3 className="text-xs font-semibold text-slate-600 mb-2">Overall Assessment</h3>
            <p className="text-sm text-slate-700">{analysis.overall_assessment}</p>
          </div>

          {/* Alignment Score */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-slate-600">Alignment Score</h3>
              <span className="text-sm font-bold text-slate-700">
                {analysis.alignment_score}/10
              </span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full transition-all ${
                  analysis.alignment_score >= 7
                    ? 'bg-emerald-500'
                    : analysis.alignment_score >= 5
                      ? 'bg-amber-500'
                      : 'bg-red-500'
                }`}
                style={{ width: `${scoreWidth}%` }}
              />
            </div>
          </div>

          {/* Top Risks */}
          <div>
            <h3 className="text-xs font-semibold text-slate-600 mb-2">⚠ Top Risks</h3>
            <ul className="space-y-1">
              {analysis.top_risks.map((risk, i) => (
                <li key={i} className="text-sm text-slate-600 flex items-start">
                  <span className="mr-2">•</span>
                  <span>{risk}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Trade Ideas */}
          <div>
            <h3 className="text-xs font-semibold text-slate-600 mb-3">💡 Trade Ideas</h3>
            <div className="space-y-2">
              {analysis.trade_ideas.map((idea, i) => {
                const colors = BADGE_COLORS[idea.action] || BADGE_COLORS.HOLD
                return (
                  <div key={i} className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg">
                    <span
                      className={`inline-block text-xs font-semibold px-2 py-1 rounded ${colors.bg} ${colors.text} whitespace-nowrap mt-0.5`}
                    >
                      {idea.action}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-700">{idea.instrument}</p>
                      <p className="text-xs text-slate-600 mt-1">{idea.rationale}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Market Context */}
          <div className="pt-4 border-t border-slate-200">
            <h3 className="text-xs font-semibold text-slate-600 mb-2">📰 Market Context</h3>
            <p className="text-sm text-slate-600 italic">{analysis.market_context}</p>
          </div>
        </div>
      )}
    </div>
  )
}
