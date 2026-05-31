/**
 * scanApi.ts
 * Typed parser for the POST /api/v1/scan response.
 * Matches the backend AnalysisResponse + DiscoveryResponse shapes.
 */

// ── Evidence types (mirrors backend evidence.py) ────────────────────────────

export interface MatchedSentence {
  original_text: string
  candidate_text: string
  original_start: number
  original_end: number
  candidate_start: number
  candidate_end: number
  original_sentence_index: number | null
  candidate_sentence_index: number | null
  similarity_score: number
  match_type: 'exact' | 'fuzzy' | 'semantic'
}

export interface MatchedParagraph {
  original_text: string
  candidate_text: string
  original_start: number
  original_end: number
  candidate_start: number
  candidate_end: number
  original_paragraph_index: number | null
  candidate_paragraph_index: number | null
  similarity_score: number
  match_type: 'exact' | 'fuzzy' | 'semantic' | 'mixed'
  matched_sentences: MatchedSentence[]
}

export interface EvidenceItem {
  candidate_url: string
  candidate_title: string | null
  domain: string
  similarity_score: number
  copied_percentage: number
  matched_paragraphs: MatchedParagraph[]
  matched_sentences: MatchedSentence[]
  high_confidence_matches: number
  notes: string | null
}

export interface EvidenceSummary {
  total_candidates: number
  total_matched_paragraphs: number
  total_matched_sentences: number
  high_confidence_matches: number
  items: EvidenceItem[]
  summary: string | null
}

// ── Discovery types ──────────────────────────────────────────────────────────

export interface DiscoveryCandidate {
  url: string
  title: string | null
  domain: string
  content: string
}

export interface DiscoveryResult {
  request_id: string
  status: 'completed' | 'partial' | 'failed'
  original_title: string | null
  queries_used: string[]
  total_urls_collected: number
  candidates: DiscoveryCandidate[]
}

// ── Analysis types ───────────────────────────────────────────────────────────

export interface SimilarityBreakdown {
  exact: number
  fuzzy: number
  semantic: number
}

export interface CandidateAnalysis {
  candidate_url: string
  candidate_title: string | null
  domain: string
  similarity_score: number
  copied_percentage: number
  breakdown: SimilarityBreakdown
  risk_level: 'low' | 'medium' | 'high'
}

export interface RiskAssessment {
  risk_level: 'low' | 'medium' | 'high'
  confidence_score: number
  reasoning: string[]
}

export interface AnalysisResult {
  analysis_id: string
  status: 'completed' | 'partial' | 'failed'
  results: CandidateAnalysis[]
  evidence: EvidenceSummary | null
  risk_assessment: RiskAssessment | null
}

// ── Unified scan response (POST /api/v1/scan) ────────────────────────────────

/** Per-source entry used by the UI display layer. */
export interface SourceEntry {
  url: string
  domain: string
  title: string | null
  match_percent: number
  classification: string
  words_matched: number
  authority: string | null
}

/** Flat summary consumed by the UI components. */
export interface ScanSummary {
  similarity: number       // 0–100
  confidence: number       // 0–100
  source_count: number
  insight: string
  sources: SourceEntry[]
}

export interface ScanResponse {
  discovery: DiscoveryResult
  analysis: AnalysisResult
  summary: ScanSummary
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function classifyCandidate(analysis: CandidateAnalysis): string {
  const pct = analysis.copied_percentage * 100
  const sim = analysis.similarity_score * 100
  if (pct >= 90 || sim >= 90) return 'EXACT COPY'
  if (pct >= 70 || sim >= 70) return 'NEAR DUPLICATE'
  if (pct >= 40 || sim >= 40) return 'MODIFIED COPY'
  if (pct >= 10 || sim >= 10) return 'PARTIAL COPY'
  return 'NO MATCH'
}

function buildInsight(risk: RiskAssessment | null, topSimilarity: number): string {
  if (!risk) return 'Analysis complete. No significant risk signals detected.'
  const level = risk.risk_level.toUpperCase()
  const pct = Math.round(topSimilarity * 100)
  const reason = risk.reasoning[0] ?? 'See evidence tab for details.'
  return `Risk level ${level} — top candidate is ${pct}% similar. ${reason}`
}

// ── Public parser ─────────────────────────────────────────────────────────────

/**
 * Normalise the raw JSON payload from POST /api/v1/scan into a typed
 * ScanResponse that the UI can consume directly.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function parseScanResponse(raw: Record<string, any>): ScanResponse {
  // Support both flat (Phase 8 combined endpoint) and nested formats
  const discovery: DiscoveryResult = raw['discovery'] ?? {
    request_id: raw['request_id'] ?? '',
    status: raw['status'] ?? 'completed',
    original_title: raw['original_title'] ?? null,
    queries_used: raw['queries_used'] ?? [],
    total_urls_collected: raw['total_urls_collected'] ?? 0,
    candidates: raw['candidates'] ?? [],
  }

  const analysisRaw = raw['analysis'] ?? raw
  const results: CandidateAnalysis[] = analysisRaw['results']
    ?? analysisRaw['similarity_results']
    ?? []

  // Backend may nest evidence under analysis.evidence or analysis.evidence_report
  // Also handle new shape where items come from analysis results directly
  const rawEvidence = analysisRaw['evidence'] ?? analysisRaw['evidence_report'] ?? null
  let evidence: EvidenceSummary | null = rawEvidence

  // If evidence has no items but we have results, synthesise minimal evidence items
  // so the Comparison tab can render something
  if (evidence && (!evidence.items || evidence.items.length === 0) && results.length > 0) {
    evidence = {
      ...evidence,
      items: results.map((r) => ({
        candidate_url: r.candidate_url,
        candidate_title: r.candidate_title ?? null,
        domain: r.domain,
        similarity_score: r.similarity_score,
        copied_percentage: r.copied_percentage,
        matched_paragraphs: [],
        matched_sentences: [],
        high_confidence_matches: 0,
        notes: null,
      })),
    }
  }

  const riskAssessment: RiskAssessment | null =
    analysisRaw['risk_assessment'] ?? null

  const analysis: AnalysisResult = {
    analysis_id: analysisRaw['analysis_id'] ?? '',
    status: analysisRaw['status'] ?? 'completed',
    results,
    evidence,
    risk_assessment: riskAssessment,
  }

  const backendSummary = raw['summary']
  if (backendSummary && Array.isArray(backendSummary['sources'])) {
    const sources: SourceEntry[] = backendSummary['sources'].map((source: Record<string, unknown>) => ({
      url: String(source['url'] ?? ''),
      domain: String(source['domain'] ?? ''),
      title: (source['title'] as string | null | undefined) ?? null,
      match_percent: Number(source['match_percent'] ?? 0),
      classification: String(source['classification'] ?? 'NO MATCH'),
      words_matched: (() => {
        const w = Number(source['words_matched'] ?? 0)
        // backend sends matched sentence count; multiply by avg sentence word count for display
        return w > 0 && w < 50 ? w * 8 : w
      })(),
      authority: source['authority'] != null ? String(source['authority']) : null,
    }))

    const summary: ScanSummary = {
      similarity: Number(backendSummary['similarity'] ?? 0),
      confidence: Number(backendSummary['confidence'] ?? 0),
      source_count: Number(backendSummary['source_count'] ?? sources.length),
      insight: String(backendSummary['insight'] ?? buildInsight(riskAssessment, 0)),
      sources,
    }

    return { discovery, analysis, summary }
  }

  // Fallback for legacy payloads without a backend summary block
  const sources: SourceEntry[] = results.map((r) => ({
    url: r.candidate_url,
    domain: r.domain,
    title: r.candidate_title ?? null,
    match_percent: Math.round(r.similarity_score * 100),
    classification: classifyCandidate(r),
    words_matched: (() => {
      const item = evidence?.items.find((i) => i.candidate_url === r.candidate_url)
      if (!item) return 0
      // Sum words across matched sentence texts as a proxy for matched word count
      return item.matched_sentences.reduce((n, ms) => n + ms.original_text.split(' ').length, 0)
        || item.matched_paragraphs.reduce((n, mp) => n + mp.original_text.split(' ').length, 0)
        || 0
    })(),
    authority: null,
  }))

  const topResult = results.length > 0
    ? results.reduce((a, b) => (a.similarity_score > b.similarity_score ? a : b))
    : null

  const topSimilarity = topResult?.similarity_score ?? 0
  const confidence = riskAssessment
    ? Math.round(riskAssessment.confidence_score * 100)
    : Math.round(topSimilarity * 100)

  const summary: ScanSummary = {
    similarity: Math.round(topSimilarity * 100),
    confidence,
    source_count: results.length,
    insight: buildInsight(riskAssessment, topSimilarity),
    sources,
  }

  return { discovery, analysis, summary }
}