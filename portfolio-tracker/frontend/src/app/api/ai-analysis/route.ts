import { NextRequest, NextResponse } from 'next/server'

interface PortfolioSummary {
  total_nav_hkd: string
  by_asset_type: Record<string, string>
}

interface AnalysisRequest {
  portfolio: PortfolioSummary
  targetAlloc?: Record<string, number>
}

interface AnalysisResult {
  overall_assessment: string
  alignment_score: number
  top_risks: string[]
  trade_ideas: Array<{ action: string; instrument: string; rationale: string }>
  market_context: string
}

const DEFAULT_TARGET_ALLOC = {
  etf_broad_index: 40,
  bond_ust: 25,
  crypto: 20,
  etf_commodity: 10,
  cash: 5,
}

async function searchTavily(query: string): Promise<string> {
  const apiKey = process.env.TAVILY_API_KEY
  if (!apiKey) throw new Error('TAVILY_API_KEY not set')

  const res = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: apiKey,
      query,
      search_depth: 'basic',
      max_results: 3,
      include_answer: true,
    }),
  })

  if (!res.ok) throw new Error(`Tavily API error: ${res.status}`)
  const data = await res.json()

  return (
    data.results
      ?.map((r: { title: string; snippet: string }) => `${r.title}: ${r.snippet}`)
      .join('\n') || ''
  )
}

async function analyzeWithGroq(
  portfolioData: string,
  newsContext: string
): Promise<AnalysisResult> {
  const apiKey = process.env.GROQ_API_KEY
  if (!apiKey) throw new Error('GROQ_API_KEY not set')

  const systemPrompt = `You are a portfolio advisor for a hedge fund employee in Hong Kong with a USD 10M retirement goal.
Compliance rules: CANNOT buy new single-name stocks or thematic ETFs (LIT, KWEB, ICLN etc).
CAN hold/buy: broad index ETFs (VT, VWRA, SPY, IVV), bond ETFs (BND, TLT, VBTLX), direct government bonds (UST/UKT), commodity ETFs, all crypto, cash.
Single-name stocks already held can be kept/sold but not added to.

Respond ONLY with valid JSON (no markdown, no code fences) matching this exact schema:
{
  "overall_assessment": "string (2-3 sentences)",
  "alignment_score": number (1-10),
  "top_risks": ["string", "string", "string"],
  "trade_ideas": [{ "action": "BUY|SELL|HOLD|REBALANCE", "instrument": "string", "rationale": "string" }],
  "market_context": "string (2-3 sentences)"
}`

  const userPrompt = `
PORTFOLIO DATA:
${portfolioData}

RECENT MARKET NEWS:
${newsContext || 'No recent news available.'}

Please analyze this portfolio against the target allocation (40% index ETFs, 25% bonds, 20% crypto, 10% commodity ETFs, 5% cash) and provide your assessment.`

  const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: 'llama-3.3-70b-versatile',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt },
      ],
      temperature: 0.3,
      max_tokens: 800,
    }),
  })

  if (!res.ok) {
    const err = await res.json()
    throw new Error(`Groq API error: ${err.error?.message || res.status}`)
  }

  const data = await res.json()
  const content = data.choices?.[0]?.message?.content || ''

  try {
    return JSON.parse(content)
  } catch (e) {
    throw new Error(`Failed to parse Groq response as JSON: ${content}`)
  }
}

export async function POST(req: NextRequest) {
  try {
    const { portfolio, targetAlloc } = (await req.json()) as AnalysisRequest

    if (!portfolio?.total_nav_hkd) {
      return NextResponse.json(
        { error: 'Portfolio data required' },
        { status: 400 }
      )
    }

    const target = targetAlloc || DEFAULT_TARGET_ALLOC
    const totalNav = parseFloat(portfolio.total_nav_hkd || '0')

    // Calculate actual allocation percentages
    const actualAlloc: Record<string, number> = {}
    for (const [k, v] of Object.entries(portfolio.by_asset_type || {})) {
      actualAlloc[k] = totalNav === 0 ? 0 : (parseFloat(v) / totalNav) * 100
    }

    // Build portfolio data string
    const portfolioData = `
Total NAV: HK$${(totalNav / 1_000_000).toFixed(1)}M

Current Allocation:
${Object.entries(actualAlloc)
  .map(([k, v]) => `  ${k}: ${v.toFixed(1)}%`)
  .join('\n')}

Target Allocation:
${Object.entries(target)
  .map(([k, v]) => `  ${k}: ${v}%`)
  .join('\n')}

Retirement Goal: USD 10M (HK$77.8M) | Status: On track to reach Year 2044
`

    // Search for relevant news (4 queries to keep costs low)
    const now = new Date()
    const monthYear = now.toLocaleString('en-US', { month: 'long', year: 'numeric' })

    const newsQueries = [
      `Bitcoin Ethereum crypto market outlook ${monthYear}`,
      `global index ETF VT VWRA outlook ${monthYear}`,
      `US Treasury bond yield outlook ${monthYear}`,
      `Hong Kong market investor news ${monthYear}`,
    ]

    const newsResults = await Promise.all(newsQueries.map((q) => searchTavily(q)))
    const newsContext = newsResults.filter((r) => r).join('\n\n---\n\n')

    // Get analysis from Groq
    const analysis = await analyzeWithGroq(portfolioData, newsContext)

    return NextResponse.json({
      analysis,
      analyzedAt: new Date().toISOString(),
    })
  } catch (error) {
    console.error('AI analysis error:', error)
    return NextResponse.json(
      { error: (error as Error).message || 'Analysis failed' },
      { status: 500 }
    )
  }
}
