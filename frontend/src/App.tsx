import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, type Variants } from 'motion/react'
import {
  Bell,
  Cpu,
  FileCheck,
  FileText,
  GitCompare,
  Globe,
  Menu,
  Play,
  Radar,
  ScanSearch,
  Search,
  Shield,
  ShieldAlert,
  Upload,
} from 'lucide-react'

import { parseScanResponse } from './lib/scanApi'
import type { ScanResponse, SourceEntry } from './lib/scanApi'

type ComparisonRow = {
  original: string
  matched: string
  matchType: string
  key: string
}

const DEMO_ARTICLE_TEXT =
  'LexTrace helps publishers detect unauthorized copies of their articles across the web. ' +
  'Paste your article text here to run discovery, similarity analysis, and evidence reporting in one scan.'

const fadeUp: Variants = {
  initial: { opacity: 0, y: 24 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] as const },
  },
}

const fadeIn: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.6, ease: 'easeOut' } },
}

const staggerContainer = (delay = 0): Variants => ({
  animate: { transition: { staggerChildren: 0.1, delayChildren: delay } },
})

const scaleIn: Variants = {
  initial: { opacity: 0, scale: 0.94 },
  animate: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as const },
  },
}

const letterBlock: Variants = {
  initial: { opacity: 0, y: 36 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] as const },
  },
}

const heroPreviewLines = [
  'w-full',
  'w-5/6',
  'w-4/5',
  'w-full',
  'w-3/4',
  'w-5/6',
]

const sectionViewport = { once: true, margin: '-80px' }

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

function parseSourceUrl(text: string) {
  try {
    const candidate = new URL(text.trim())
    return candidate.href
  } catch {
    return undefined
  }
}

function riskFromScore(score: number): 'Low' | 'Medium' | 'High' | 'Critical' {
  if (score >= 90) return 'Critical'
  if (score >= 70) return 'High'
  if (score >= 40) return 'Medium'
  if (score >= 10) return 'Low'
  return 'Low'
}

function sourceBadgeClass(classification: string) {
  if (classification === 'EXACT COPY') {
    return 'border-red-500/30 bg-red-500/15 text-red-400'
  }
  if (classification === 'NEAR DUPLICATE') {
    return 'border-orange-500/30 bg-orange-500/15 text-orange-400'
  }
  if (classification === 'MODIFIED COPY') {
    return 'border-yellow-500/30 bg-yellow-500/15 text-yellow-400'
  }
  if (classification === 'PARTIAL COPY') {
    return 'border-sky-500/30 bg-sky-500/15 text-sky-400'
  }
  return 'border-white/10 bg-white/5 text-[--color-muted]'
}

function App() {
  const [activeTab, setActiveTab] = useState<
    'analysis' | 'discovery' | 'comparison' | 'history'
  >('analysis')
  const [scanProgress, setScanProgress] = useState(0)
  const [showScanResult, setShowScanResult] = useState(false)
  const [inputText, setInputText] = useState('')
  const [isScanning, setIsScanning] = useState(false)
  const [backendError, setBackendError] = useState<string | null>(null)
  const [liveScan, setLiveScan] = useState<ScanResponse | null>(null)
  const scanTimerRef = useRef<number | null>(null)
  const dashboardRef = useRef<HTMLElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToDashboard = () => {
    dashboardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const focusDashboardInput = () => {
    scrollToDashboard()
    window.setTimeout(() => textareaRef.current?.focus(), 350)
  }

  const handleNavClick = (target: string) => {
    const sectionIds: Record<string, string> = {
      Features: 'features',
      'How It Works': 'how-it-works',
      Dashboard: 'dashboard',
      Pricing: 'pricing',
    }
    document.getElementById(sectionIds[target] ?? '')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
  }

  const handleNewScan = () => {
    setActiveTab('analysis')
    setShowScanResult(false)
    setBackendError(null)
    setInputText('')
    setLiveScan(null)
    setScanProgress(0)
    setIsScanning(false)
    focusDashboardInput()
  }

  const handleViewDemo = () => {
    setActiveTab('analysis')
    setInputText(DEMO_ARTICLE_TEXT)
    setShowScanResult(false)
    setBackendError(null)
    scrollToDashboard()
    window.setTimeout(() => textareaRef.current?.focus(), 350)
  }

  const handleStartAnalysis = () => {
    scrollToDashboard()
    if (inputText.trim().length >= 100) {
      handleAnalyze()
      return
    }
    focusDashboardInput()
  }

  useEffect(() => {
    return () => {
      if (scanTimerRef.current !== null) {
        window.clearInterval(scanTimerRef.current)
      }
    }
  }, [])

  const handleAnalyze = () => {
    if (isScanning) {
      return
    }

    const articleText = inputText.trim()

    if (articleText.length < 100) {
      setBackendError('Paste at least 100 characters so the backend can run discovery.')
      setShowScanResult(false)
      scrollToDashboard()
      return
    }

    setIsScanning(true)
    setScanProgress(0)
    setShowScanResult(false)
    setBackendError(null)
    setLiveScan(null)

    const start = window.performance.now()

    if (scanTimerRef.current !== null) {
      window.clearInterval(scanTimerRef.current)
    }

    scanTimerRef.current = window.setInterval(() => {
      const elapsed = window.performance.now() - start
      const progress = Math.min(90, Math.round((elapsed / 2200) * 90))
      setScanProgress(progress)
    }, 40)

    void (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/scan`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            article_text: articleText,
            source_url: parseSourceUrl(articleText),
          }),
        })

        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as { detail?: string } | null
          throw new Error(payload?.detail ?? `Backend request failed (${response.status})`)
        }

        const payload = await response.json()
        const data = parseScanResponse(payload)
        setLiveScan(data)
        setShowScanResult(true)
        setScanProgress(100)
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Backend request failed.'
        setBackendError(message)
        setShowScanResult(false)
        setScanProgress(0)
      } finally {
        if (scanTimerRef.current !== null) {
          window.clearInterval(scanTimerRef.current)
          scanTimerRef.current = null
        }
        setIsScanning(false)
      }
    })()
  }

  const metricStroke = useMemo(() => {
    const radius = 32
    const circumference = 2 * Math.PI * radius
    const similarity = liveScan?.summary.similarity ?? 0

    return {
      radius,
      circumference,
      offset: circumference * (1 - similarity / 100),
    }
  }, [liveScan])

  const displayResults = useMemo(() => {
    const summary = liveScan?.summary
    const similarity = summary?.similarity ?? 0
    const confidence = summary?.confidence ?? 0
    const sourceCount = summary?.source_count ?? 0
    const matchedWords = summary?.sources.reduce((total: number, source: SourceEntry) => total + source.words_matched, 0) ?? 0

    return {
      similarity,
      confidence,
      riskLevel: riskFromScore(similarity),
      sourcesFound: sourceCount,
      matchedWords,
    }
  }, [liveScan])

  const displaySources = useMemo(() => liveScan?.summary.sources ?? [], [liveScan])

  const matchedSources = useMemo(
    () => displaySources.filter((source: SourceEntry) => source.classification !== 'NO MATCH'),
    [displaySources],
  )

  const candidateSources = useMemo(
    () => displaySources.filter((source: SourceEntry) => source.classification === 'NO MATCH'),
    [displaySources],
  )

  const topEvidence = liveScan?.analysis.evidence?.items[0] ?? null

  return (
    <div className="min-h-screen bg-[--color-bg] text-[--color-text]">
      <motion.nav
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0, transition: { delay: 0.1 } }}
        className="fixed left-0 right-0 top-0 z-50 flex items-center justify-between border-b border-[--color-border] bg-[rgba(5,7,15,0.8)] px-6 py-4 backdrop-blur-xl md:px-12"
      >
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2 text-[18px] font-extrabold tracking-[-0.02em] text-white">
              <span className="text-[--color-blue]">◈</span>
              <span className="font-display">LEXTRACE</span>
            </div>
            <div className="text-[9px] font-mono uppercase tracking-[0.25em] text-[--color-muted]">
              CONTENT INTELLIGENCE
            </div>
          </div>
        </div>

        <div className="hidden items-center gap-8 md:flex">
          {['Features', 'How It Works', 'Dashboard', 'Pricing'].map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => handleNavClick(item)}
              className="text-[13px] text-[--color-muted] transition hover:text-white"
            >
              {item}
            </button>
          ))}
        </div>

        <div className="hidden items-center gap-4 md:flex">
          <button
            type="button"
            onClick={scrollToDashboard}
            className="text-[13px] text-[--color-muted] transition hover:text-white"
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={handleStartAnalysis}
            className="rounded-md bg-[--color-blue] px-4 py-2 text-[13px] font-medium text-white transition hover:bg-[--color-blue-bright]"
          >
            Start Free Trial
          </button>
        </div>

        <div className="md:hidden">
          <Menu size={20} className="text-white" />
        </div>
      </motion.nav>

      <section className="relative flex min-h-screen w-full flex-col items-center justify-center px-6 pb-16 pt-24 text-center">
        <div className="pointer-events-none absolute -left-40 -top-40 h-150 w-150 rounded-full bg-[radial-gradient(circle,rgba(37,99,255,0.12)_0%,transparent_70%)]" />
        <div className="pointer-events-none absolute -right-40 -top-20 h-150 w-150 rounded-full bg-[radial-gradient(circle,rgba(124,58,237,0.08)_0%,transparent_70%)]" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-100 w-200 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(ellipse,rgba(37,99,255,0.06)_0%,transparent_60%)]" />

        <div className="pointer-events-none absolute inset-0 opacity-60">
          <svg className="h-full w-full" aria-hidden="true">
            <defs>
              <pattern
                id="grid"
                width="60"
                height="60"
                patternUnits="userSpaceOnUse"
              >
                <path d="M 60 0 L 0 0 0 60" stroke="rgba(255,255,255,0.03)" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>
        </div>
        <ScanningBeam />

        <motion.div
          className="relative z-10 inline-flex items-center gap-2 rounded-full border border-[--color-blue]/30 bg-[--color-blue]/10 px-3 py-1.5"
          variants={fadeIn}
          initial="initial"
          animate="animate"
        >
          <motion.span
            className="h-1.5 w-1.5 rounded-full bg-[--color-cyan]"
            animate={{ scale: [1, 1.4, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <span className="text-[11px] font-mono uppercase tracking-[0.15em] text-[--color-cyan]">
            AI-Powered Content Intelligence
          </span>
        </motion.div>

        <motion.div
          className="relative z-10 mt-8"
          variants={staggerContainer(0.2)}
          initial="initial"
          animate="animate"
        >
          <motion.h1
            className="font-display text-[14vw] font-extrabold leading-[0.88] tracking-[-0.04em] text-white md:text-[11vw] lg:text-[10vw]"
            variants={letterBlock}
          >
            TRACE
          </motion.h1>
          <motion.div variants={letterBlock} className="mt-2">
            <h1 className="font-display text-[14vw] font-extrabold leading-[0.88] tracking-[-0.04em] text-white md:text-[11vw] lg:text-[10vw]">
              TRUTH
            </h1>
            <div className="mx-auto mt-2 h-0.75 w-full max-w-130 bg-linear-to-r from-[--color-blue] via-[--color-violet] to-[--color-cyan]" />
          </motion.div>
        </motion.div>

        <motion.p
          className="relative z-10 mt-8 max-w-130 text-[15px] leading-[1.65] text-[--color-muted] md:text-[17px]"
          variants={fadeUp}
          initial="initial"
          animate="animate"
          transition={{ delay: 0.5 }}
        >
          AI-powered content intelligence that discovers copied articles, unauthorized
          reposts, plagiarism, and digital piracy across the web.
        </motion.p>

        <motion.div
          className="relative z-10 mt-10 flex flex-wrap items-center justify-center gap-4"
          variants={fadeUp}
          initial="initial"
          animate="animate"
          transition={{ delay: 0.6 }}
        >
          <button
            type="button"
            onClick={handleStartAnalysis}
            className="group inline-flex items-center gap-2 rounded-md bg-[--color-blue] px-6 py-3 text-[14px] font-medium text-white transition hover:-translate-y-0.5 hover:bg-[--color-blue-bright] hover:shadow-[0_8px_30px_rgba(37,99,255,0.4)]"
          >
            <Search size={16} />
            Analyze Content
          </button>
          <button
            type="button"
            onClick={handleViewDemo}
            className="group inline-flex items-center gap-2 rounded-md border border-[--color-border] px-6 py-3 text-[14px] text-[--color-muted] transition hover:-translate-y-0.5 hover:border-white/20 hover:text-white"
          >
            <Play size={16} />
            View Demo
          </button>
        </motion.div>

        <motion.div
          className="relative z-10 mt-16 flex flex-wrap items-center justify-center gap-8 md:gap-16"
          variants={fadeUp}
          initial="initial"
          animate="animate"
          transition={{ delay: 0.7 }}
        >
          {[
            { value: '2.4B+', label: 'Web pages scanned' },
            { value: '99.2%', label: 'Detection accuracy' },
            { value: '< 3s', label: 'Analysis time' },
          ].map((stat, index) => (
            <div key={stat.label} className="flex items-center gap-8">
              <div className="text-center">
                <div className="font-display text-[28px] font-bold text-white">
                  {stat.value}
                </div>
                <div className="text-[11px] font-mono uppercase tracking-[0.15em] text-[--color-muted]">
                  {stat.label}
                </div>
              </div>
              {index < 2 && (
                <div className="hidden h-12 w-px bg-[--color-border] md:block" />
              )}
            </div>
          ))}
        </motion.div>

        <motion.div
          className="relative z-10 mt-20 w-full max-w-215"
          variants={scaleIn}
          initial="initial"
          animate="animate"
          transition={{ delay: 0.8 }}
        >
          <motion.div
            whileHover={{ y: -4 }}
            className="relative overflow-hidden rounded-xl border border-[--color-border] bg-[linear-gradient(135deg,rgba(8,12,24,0.9),rgba(5,7,15,0.95))] shadow-[0_40px_100px_rgba(0,0,0,0.6),0_0_0_1px_rgba(37,99,255,0.1),inset_0_1px_0_rgba(255,255,255,0.04)]"
          >
            <div className="absolute left-0 right-0 top-0 h-px bg-linear-to-r from-transparent via-[--color-blue]/50 to-transparent" />
            <div className="flex items-center gap-3 border-b border-[--color-border] px-5 py-3">
              <div className="flex gap-2">
                <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                <span className="h-3 w-3 rounded-full bg-[#ffbd2e]" />
                <span className="h-3 w-3 rounded-full bg-[#28c840]" />
              </div>
              <div className="flex-1 text-center text-[11px] font-mono tracking-widest text-[--color-muted]">
                lextrace.io/analyze
              </div>
              <Shield size={14} className="text-[--color-cyan]" />
            </div>
            <div className="grid grid-cols-3 gap-0">
              <div className="col-span-2 border-r border-[--color-border] p-5">
                <div className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-[--color-muted]">
                  CONTENT INPUT
                </div>
                <div className="space-y-2">
                  {heroPreviewLines.map((width, index) => (
                    <div
                      key={`${width}-${index}`}
                      className={`h-2 rounded-full bg-white/10 ${width}`}
                    />
                  ))}
                  <div className="space-y-2">
                    <div className="h-2 rounded-full border-l-2 border-[--color-blue] bg-[--color-blue]/20" />
                    <div className="h-2 rounded-full border-l-2 border-[--color-blue] bg-[--color-blue]/20" />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleStartAnalysis}
                  className="mt-4 w-full rounded bg-[--color-blue] py-2 text-center text-[11px] font-mono text-white transition hover:bg-[--color-blue-bright]"
                >
                  Analyze Content
                </button>
              </div>
              <div className="p-5">
                <div className="flex items-center gap-4">
                  <svg width="80" height="80" className="text-white">
                    <circle
                      cx="40"
                      cy="40"
                      r={metricStroke.radius}
                      stroke="rgba(255,255,255,0.08)"
                      strokeWidth="3"
                      fill="none"
                    />
                    <motion.circle
                      cx="40"
                      cy="40"
                      r={metricStroke.radius}
                      stroke="#2563ff"
                      strokeWidth="3"
                      strokeDasharray={metricStroke.circumference}
                      strokeDashoffset={metricStroke.circumference}
                      fill="none"
                      animate={{ strokeDashoffset: metricStroke.offset }}
                      transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </svg>
                  <div>
                    <div className="text-[16px] font-bold text-white">
                      {displayResults.similarity.toFixed(1)}%
                    </div>
                    <div className="text-[9px] font-mono text-[--color-muted]">
                      Similarity
                    </div>
                  </div>
                </div>
                <div className="mt-4">
                  <RiskBadge level="Critical" />
                </div>
                <div className="mt-4">
                  <div className="text-[20px] font-bold text-[--color-cyan]">12</div>
                  <div className="text-[9px] font-mono text-[--color-muted]">
                    Sources Detected
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </section>

      <motion.section
        id="features"
        className="relative z-20 w-full px-6 py-32 md:px-12"
        variants={fadeUp}
        initial="initial"
        whileInView="animate"
        viewport={sectionViewport}
      >
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-[--color-blue]">
          [ 01 ] Core Features
        </div>
        <h2 className="mt-4 max-w-150 font-display text-[2.4rem] font-bold leading-[1.1] tracking-[-0.03em] text-white md:text-[3.2rem]">
          Everything you need to protect your content
        </h2>
        <p className="mt-4 max-w-120 text-[15px] text-[--color-muted]">
          From discovery to DMCA-ready evidence in one unified platform.
        </p>
        <motion.div
          className="mt-16 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
          variants={staggerContainer(0.1)}
          initial="initial"
          whileInView="animate"
          viewport={sectionViewport}
        >
          {[
            {
              icon: ScanSearch,
              title: 'Similarity Analysis',
              description:
                'AI calculates exact similarity percentages, match confidence, and content overlap across billions of web pages.',
              tag: 'AI-POWERED',
            },
            {
              icon: Globe,
              title: 'Source Discovery',
              description:
                'Scans the web to find every site that published your content — exact copies, near-duplicates, and modified reposts.',
              tag: 'WEB-SCALE',
            },
            {
              icon: FileText,
              title: 'Evidence Reports',
              description:
                'Generate professional PDF reports with matched excerpts, screenshots, timestamps, and legal-grade evidence packages.',
              tag: 'EXPORT READY',
            },
            {
              icon: GitCompare,
              title: 'Content Comparison',
              description:
                'Side-by-side diff view highlights exact matches, rewritten sections, and added content with color-coded precision.',
              tag: 'VISUAL DIFF',
            },
            {
              icon: ShieldAlert,
              title: 'Risk Scoring',
              description:
                'AI assigns Low / Medium / High / Critical risk levels based on similarity, domain authority, and copy depth.',
              tag: 'RISK INTEL',
            },
            {
              icon: Bell,
              title: 'Monitoring',
              description:
                'Track your content over time. Get alerts when new copies appear, sources change, or repeat offenders strike again.',
              tag: 'REAL-TIME',
            },
          ].map((feature) => (
            <motion.div
              key={feature.title}
              variants={fadeUp}
              className="rounded-xl border border-[--color-border] bg-[linear-gradient(135deg,rgba(8,12,24,0.8),rgba(5,7,15,0.6))] p-6 transition hover:-translate-y-0.5 hover:border-[--color-blue]/30"
            >
              <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-lg border border-[--color-blue]/20 bg-[linear-gradient(135deg,rgba(37,99,255,0.2),rgba(124,58,237,0.1))]">
                <feature.icon size={18} className="text-[--color-blue]" />
              </div>
              <div className="text-[15px] font-semibold text-white">
                {feature.title}
              </div>
              <p className="mt-2 text-[13px] leading-[1.6] text-[--color-muted]">
                {feature.description}
              </p>
              <div className="mt-4 text-[10px] font-mono uppercase tracking-[0.15em] text-[--color-blue]/60">
                {feature.tag}
              </div>
            </motion.div>
          ))}
        </motion.div>

        <motion.div
          className="mt-8 flex flex-col gap-6 rounded-xl border border-[--color-border] bg-[linear-gradient(135deg,rgba(8,12,24,0.8),rgba(5,7,15,0.6))] p-8 md:flex-row md:items-center md:justify-between md:p-12"
          variants={fadeUp}
          initial="initial"
          whileInView="animate"
          viewport={sectionViewport}
        >
          <h3 className="max-w-105 font-display text-[1.6rem] font-bold leading-[1.2] text-white md:text-[2.2rem]">
            Powered by semantic AI — not just keyword matching
          </h3>
          <div className="max-w-105 text-[13px] leading-[1.7] text-[--color-muted]">
            LexTrace builds a semantic fingerprint of your content, revealing when
            articles are rewritten, paraphrased, or syndicated without permission.
            <button
              type="button"
              onClick={() => handleNavClick('How It Works')}
              className="mt-4 text-[--color-blue] transition hover:text-[--color-blue-bright]"
            >
              Learn More →
            </button>
          </div>
        </motion.div>
      </motion.section>

      <motion.section
        id="how-it-works"
        className="relative w-full border-y border-[--color-border] bg-[--color-surface] px-6 py-32 md:px-12"
        variants={fadeUp}
        initial="initial"
        whileInView="animate"
        viewport={sectionViewport}
      >
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-[--color-blue]">
          [ 02 ] How It Works
        </div>
        <h2 className="mt-4 font-display text-[2.4rem] font-bold leading-[1.1] tracking-[-0.03em] text-white md:text-[3.2rem]">
          From paste to proof in seconds
        </h2>
        <p className="mt-4 max-w-120 text-[15px] text-[--color-muted]">
          A streamlined workflow designed for editorial, legal, and compliance teams.
        </p>

        <div className="mt-16 flex flex-col gap-8 md:flex-row md:items-start md:gap-0">
          <div className="hidden flex-1 border-t border-dashed border-[--color-border] md:block" />
          {[
            {
              step: 'STEP 01',
              icon: Upload,
              title: 'Submit Content',
              description: 'Paste text, enter a URL, or upload a document',
            },
            {
              step: 'STEP 02',
              icon: Radar,
              title: 'Scan the Web',
              description: 'LexTrace searches billions of pages for matches',
            },
            {
              step: 'STEP 03',
              icon: Cpu,
              title: 'AI Analysis',
              description: 'Semantic AI calculates similarity and risk scores',
            },
            {
              step: 'STEP 04',
              icon: FileCheck,
              title: 'Get Evidence',
              description: 'Download your full report with legal-grade evidence',
            },
          ].map((step) => (
            <div
              key={step.step}
              className="flex max-w-55 flex-1 flex-col"
            >
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-[--color-blue]">
                {step.step}
              </div>
              <div className="mt-3 flex h-12 w-12 items-center justify-center rounded-full border border-[--color-blue]/30 bg-[--color-blue]/10">
                <step.icon size={20} className="text-[--color-blue]" />
              </div>
              <div className="mt-4 text-[16px] font-semibold text-white">
                {step.title}
              </div>
              <p className="mt-2 text-[13px] leading-[1.6] text-[--color-muted]">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </motion.section>

      <motion.section
        id="dashboard"
        ref={dashboardRef}
        className="relative w-full scroll-mt-24 px-6 py-32 md:px-12"
        variants={fadeUp}
        initial="initial"
        whileInView="animate"
        viewport={sectionViewport}
      >
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-[--color-blue]">
          [ 03 ] Live Dashboard
        </div>
        <h2 className="mt-4 font-display text-[2.4rem] font-bold leading-[1.1] tracking-[-0.03em] text-white md:text-[3.2rem]">
          See LexTrace in action
        </h2>
        <p className="mt-4 max-w-120 text-[15px] text-[--color-muted]">
          A real-time command center for similarity scores, discovery, and evidence.
        </p>

        <div className="mx-auto mt-12 w-full max-w-275 overflow-hidden rounded-xl border border-[--color-border] bg-[--color-surface]">
          <div className="flex items-center justify-between border-b border-[--color-border] px-6 py-3">
            <div className="flex flex-wrap gap-6 text-[12px] font-mono uppercase tracking-widest">
              {[
                { label: 'Similarity Analysis', value: 'analysis' },
                { label: 'Source Discovery', value: 'discovery' },
                { label: 'Comparison', value: 'comparison' },
                { label: 'Scan History', value: 'history' },
              ].map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  onClick={() => setActiveTab(tab.value as typeof activeTab)}
                  className={`pb-3 transition ${
                    activeTab === tab.value
                      ? 'border-b-2 border-[--color-blue] text-white'
                      : 'text-[--color-muted] hover:text-white'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={handleNewScan}
              className="rounded-md bg-[--color-blue] px-3 py-1 text-[11px] font-medium text-white transition hover:bg-[--color-blue-bright]"
            >
              New Scan
            </button>
          </div>

          {activeTab === 'analysis' && (
            <div className="grid grid-cols-1 gap-0 md:grid-cols-5">
              <div className="col-span-3 border-b border-[--color-border] p-5 md:border-b-0 md:border-r">
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-[--color-muted]">
                  CONTENT INPUT
                </div>
                <textarea
                  ref={textareaRef}
                  value={inputText}
                  onChange={(event) => setInputText(event.target.value)}
                  placeholder="Paste at least 100 characters of article text, or a URL plus article text."
                  className="mt-4 min-h-50 w-full rounded-lg border border-[--color-border] bg-[rgba(255,255,255,0.02)] p-4 text-[13px] font-mono leading-[1.7] text-[--color-muted] focus:border-[--color-blue]/40 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleAnalyze}
                  disabled={isScanning}
                  className={`mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md bg-[--color-blue] px-4 py-2 text-[12px] font-mono uppercase tracking-[0.15em] text-white transition ${
                    isScanning
                      ? 'cursor-not-allowed opacity-70'
                      : 'hover:bg-[--color-blue-bright]'
                  }`}
                >
                  <ScanSearch size={16} />
                  {isScanning ? 'Scanning...' : 'Analyze Now'}
                </button>
                <div className="mt-4 h-0.5 w-full overflow-hidden rounded-full bg-[--color-border]">
                  <div
                    className="h-full bg-linear-to-r from-[--color-blue] to-[--color-cyan]"
                    style={{ width: `${scanProgress}%` }}
                  />
                </div>
                {backendError && (
                  <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-[12px] leading-[1.6] text-red-300">
                    {backendError}
                  </div>
                )}
              </div>
              <div className="col-span-2 p-5">
                <AnimatePresence mode="wait">
                  {!showScanResult && (
                    <motion.div
                      key="placeholder"
                      variants={fadeIn}
                      initial="initial"
                      animate="animate"
                      exit={{ opacity: 0 }}
                      className="flex h-full flex-col items-center justify-center text-center text-[--color-muted]"
                    >
                      <ShieldAlert size={26} className="mb-3 text-[--color-muted]" />
                      <p className="text-[13px]">
                        Run an analysis to see results
                      </p>
                    </motion.div>
                  )}
                  {showScanResult && (
                    <motion.div
                      key="results"
                      variants={scaleIn}
                      initial="initial"
                      animate="animate"
                      exit={{ opacity: 0 }}
                    >
                      <div className="flex items-center gap-6">
                        <svg width="120" height="120">
                          <circle
                            cx="60"
                            cy="60"
                            r="50"
                            stroke="rgba(255,255,255,0.08)"
                            strokeWidth="4"
                            fill="none"
                          />
                          <motion.circle
                            cx="60"
                            cy="60"
                            r="50"
                            stroke="#2563ff"
                            strokeWidth="4"
                            strokeDasharray={2 * Math.PI * 50}
                            strokeDashoffset={2 * Math.PI * 50}
                            fill="none"
                            animate={{
                              strokeDashoffset:
                                2 * Math.PI * 50 * (1 - displayResults.similarity / 100),
                            }}
                            transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] as const }}
                          />
                        </svg>
                        <div>
                          <div className="text-[28px] font-bold text-white">
                            {displayResults.similarity.toFixed(1)}% Similarity
                          </div>
                          <RiskBadge level={displayResults.riskLevel} />
                        </div>
                      </div>
                      <div className="mt-6 grid grid-cols-3 gap-4 text-[11px] text-[--color-muted]">
                        <div>
                          <div className="text-[14px] font-semibold text-white">
                            {displayResults.confidence}%
                          </div>
                          Confidence
                        </div>
                        <div>
                          <div className="text-[14px] font-semibold text-white">
                            {displayResults.sourcesFound}
                          </div>
                          Sources
                        </div>
                        <div>
                          <div className="text-[14px] font-semibold text-white">
                            {displayResults.matchedWords}
                          </div>
                          Words Matched
                        </div>
                      </div>
                      <div className="mt-4 rounded-lg border border-[--color-blue]/20 bg-[--color-blue]/10 p-4 text-[12px] leading-[1.6] text-[--color-blue-bright]">
                        <div className="mb-2 flex items-center gap-2">
                          <ShieldAlert size={14} />
                          AI Insight
                        </div>
                        {liveScan?.summary.insight ?? 'Run an analysis to see backend-derived insights.'}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          )}

          {activeTab === 'discovery' && (
            <div className="p-6">
              {displaySources.length === 0 ? (
                <div className="rounded-xl border border-[--color-border] bg-[rgba(255,255,255,0.02)] p-6 text-[13px] text-[--color-muted]">
                  No sources were returned by the backend for this scan.
                </div>
              ) : (
                <div className="space-y-8">
                  <div>
                    <div className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-[--color-blue]">
                      Matched Sources
                    </div>
                    <div className="grid grid-cols-6 gap-4 border-b border-[--color-border] pb-3 text-[10px] font-mono uppercase tracking-[0.15em] text-[--color-muted]">
                      <div className="col-span-2">Source</div>
                      <div>Match %</div>
                      <div>Classification</div>
                      <div>Words</div>
                      <div>Authority</div>
                    </div>
                    <motion.div
                      className="mt-4 space-y-4"
                      variants={staggerContainer(0.05)}
                      initial="initial"
                      animate="animate"
                    >
                      {matchedSources.map((source: SourceEntry) => (
                        <motion.div
                          key={source.url}
                          variants={fadeUp}
                          className="grid grid-cols-6 items-center gap-4 border-b border-[--color-border] py-4 text-[12px] text-white transition hover:bg-white/2"
                        >
                          <div className="col-span-2 flex items-center gap-2 font-mono text-[13px]">
                            <Globe size={14} className="text-[--color-muted]" />
                            <span className="truncate">{source.domain}</span>
                          </div>
                          <div
                            className={`text-[12px] font-semibold ${
                              source.match_percent >= 90
                                ? 'text-red-400'
                                : source.match_percent >= 70
                                  ? 'text-orange-400'
                                  : source.match_percent >= 40
                                    ? 'text-yellow-400'
                                    : 'text-sky-400'
                            }`}
                          >
                            {source.match_percent}%
                          </div>
                          <div>
                            <span
                              className={`rounded-full border px-2 py-1 text-[10px] font-mono uppercase tracking-widest ${sourceBadgeClass(
                                source.classification,
                              )}`}
                            >
                              {source.classification}
                            </span>
                          </div>
                          <div className="text-[12px] text-[--color-muted]">
                            {source.words_matched}
                          </div>
                          <div className="font-mono text-[12px] text-[--color-muted]">
                            {source.authority ?? '—'}
                          </div>
                        </motion.div>
                      ))}
                    </motion.div>
                  </div>

                  <div>
                    <div className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-[--color-blue]">
                      Candidate Sources
                    </div>
                    <div className="grid grid-cols-6 gap-4 border-b border-[--color-border] pb-3 text-[10px] font-mono uppercase tracking-[0.15em] text-[--color-muted]">
                      <div className="col-span-2">Source</div>
                      <div>Match %</div>
                      <div>Classification</div>
                      <div>Words</div>
                      <div>Authority</div>
                    </div>
                    <motion.div
                      className="mt-4 space-y-4"
                      variants={staggerContainer(0.05)}
                      initial="initial"
                      animate="animate"
                    >
                      {candidateSources.map((source: SourceEntry) => (
                        <motion.div
                          key={source.url}
                          variants={fadeUp}
                          className="grid grid-cols-6 items-center gap-4 border-b border-[--color-border] py-4 text-[12px] text-white transition hover:bg-white/2"
                        >
                          <div className="col-span-2 flex items-center gap-2 font-mono text-[13px]">
                            <Globe size={14} className="text-[--color-muted]" />
                            <span className="truncate">{source.domain}</span>
                          </div>
                          <div className="text-[12px] font-semibold text-[--color-muted]">
                            {source.match_percent}%
                          </div>
                          <div>
                            <span
                              className={`rounded-full border px-2 py-1 text-[10px] font-mono uppercase tracking-widest ${sourceBadgeClass(
                                source.classification,
                              )}`}
                            >
                              {source.classification}
                            </span>
                          </div>
                          <div className="text-[12px] text-[--color-muted]">
                            {source.words_matched}
                          </div>
                          <div className="font-mono text-[12px] text-[--color-muted]">
                            {source.authority ?? '—'}
                          </div>
                        </motion.div>
                      ))}
                    </motion.div>
                  </div>
                </div>
              )}
              <div className="mt-4 text-[12px] text-[--color-blue]">
                View All {displayResults.sourcesFound} Sources →
              </div>
            </div>
          )}

          {activeTab === 'comparison' && (
            <div className="p-6">
              <div className="grid grid-cols-2 gap-4 border-b border-[--color-border] pb-3 text-[11px] font-mono uppercase tracking-[0.15em] text-[--color-muted]">
                <div>Original Content</div>
                <div>Matched Content</div>
              </div>
              {topEvidence ? (
                <div className="mt-4 space-y-4">
                  {(topEvidence.matched_paragraphs.length > 0
                    ? topEvidence.matched_paragraphs.map((entry, index) => ({
                        original: entry.original_text,
                        matched: entry.candidate_text,
                        matchType: entry.match_type,
                        key: `${entry.match_type}-${index}`,
                      }))
                    : topEvidence.matched_sentences.map((entry, index) => ({
                        original: entry.original_text,
                        matched: entry.candidate_text,
                        matchType: entry.match_type,
                        key: `${entry.match_type}-${index}`,
                      }))
                  ).map((entry: ComparisonRow) => (
                    <div key={entry.key} className="grid grid-cols-2 gap-4">
                      <div
                        className={`rounded-r px-3 py-2 text-[13px] leading-[1.65] ${
                          entry.matchType === 'exact'
                            ? 'border-l-2 border-red-500 bg-red-500/10 text-[--color-text]'
                            : entry.matchType === 'mixed' || entry.matchType === 'semantic'
                              ? 'border-l-2 border-yellow-500/70 bg-yellow-500/10 text-[--color-text]'
                              : 'border-l-2 border-[--color-blue] bg-[--color-blue]/10 text-[--color-text]'
                        }`}
                      >
                        {entry.original}
                      </div>
                      <div
                        className={`rounded-r px-3 py-2 text-[13px] leading-[1.65] ${
                          entry.matchType === 'exact'
                            ? 'border-l-2 border-red-500 bg-red-500/10 text-[--color-text]'
                            : entry.matchType === 'mixed' || entry.matchType === 'semantic'
                              ? 'border-l-2 border-yellow-500/70 bg-yellow-500/10 text-[--color-text]'
                              : 'border-l-2 border-dashed border-[--color-border] text-[--color-muted]'
                        }`}
                      >
                        {entry.matched}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-xl border border-[--color-border] bg-[rgba(255,255,255,0.02)] p-6 text-[13px] text-[--color-muted]">
                  Run a scan to see backend evidence comparisons.
                </div>
              )}
              <div className="mt-6 flex flex-wrap gap-4 text-[11px] font-mono uppercase tracking-[0.12em] text-[--color-muted]">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-red-400" /> Exact Match
                </div>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-yellow-400" /> Modified
                </div>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-[--color-blue]" /> Original Only
                </div>
              </div>
            </div>
          )}

          {activeTab === 'history' && (
            <div className="p-6">
              {liveScan ? (
                <div className="space-y-4">
                  <div className="flex flex-col gap-4 border-b border-[--color-border] py-5 md:flex-row md:items-center md:justify-between">
                    <div className="flex items-start gap-3">
                      <FileText size={18} className="text-[--color-muted]" />
                      <div>
                        <div className="text-[14px] font-medium text-white">
                          {liveScan.discovery.original_title ?? 'Current Scan'}
                        </div>
                        <div className="text-[11px] font-mono text-[--color-muted]">
                          {liveScan.discovery.request_id}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="h-1.5 w-32 rounded-full bg-[--color-border]">
                        <div
                          className={`h-full rounded-full ${
                            displayResults.similarity >= 90
                              ? 'bg-red-500'
                              : displayResults.similarity >= 70
                                ? 'bg-orange-500'
                                : displayResults.similarity >= 40
                                  ? 'bg-yellow-500'
                                  : 'bg-green-500'
                          }`}
                          style={{ width: `${displayResults.similarity.toFixed(1)}%` }}
                        />
                      </div>
                      <RiskBadge level={displayResults.riskLevel} />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-[--color-border] bg-[rgba(255,255,255,0.02)] p-6 text-[13px] text-[--color-muted]">
                  No scan history is loaded yet. Run an analysis to create the first backend-backed result.
                </div>
              )}
            </div>
          )}
        </div>
      </motion.section>

      <motion.section
        className="border-y border-[--color-border] px-6 py-24 md:px-12"
        variants={fadeUp}
        initial="initial"
        whileInView="animate"
        viewport={sectionViewport}
      >
        <div className="text-center text-[10px] font-mono uppercase tracking-[0.25em] text-[--color-muted]">
          TRUSTED BY CONTENT TEAMS WORLDWIDE
        </div>
        <div className="mt-12 flex flex-wrap items-center justify-center gap-10 text-[18px] font-bold text-[--color-muted] opacity-40 md:gap-16">
          {['NEXUS MEDIA', 'VERITAS POST', 'ATLAS DIGITAL', 'KRONOS WIRE', 'SENTINEL INK'].map(
            (brand) => (
              <span key={brand} className="font-display">
                {brand}
              </span>
            ),
          )}
        </div>
      </motion.section>

      <motion.section
        id="pricing"
        className="relative overflow-hidden px-6 py-40 text-center md:px-12"
        variants={fadeUp}
        initial="initial"
        whileInView="animate"
        viewport={sectionViewport}
      >
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_50%,rgba(37,99,255,0.12),transparent)]" />
        <div className="relative z-10 mx-auto max-w-160">
          <div className="inline-flex items-center gap-2 rounded-full border border-[--color-blue]/30 bg-[--color-blue]/10 px-3 py-1.5">
            <motion.span
              className="h-1.5 w-1.5 rounded-full bg-[--color-cyan]"
              animate={{ scale: [1, 1.4, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <span className="text-[11px] font-mono uppercase tracking-[0.15em] text-[--color-cyan]">
              START PROTECTING YOUR CONTENT
            </span>
          </div>
          <h2 className="mt-8 font-display text-[3rem] font-extrabold leading-[1.05] tracking-[-0.04em] text-white md:text-[5rem]">
            Protect Your Content
            <br />
            Before It Spreads.
          </h2>
          <p className="mt-6 text-[16px] text-[--color-muted]">
            Detect infringements, prove ownership, and respond faster than the
            copycats.
          </p>
          <button
            type="button"
            onClick={handleStartAnalysis}
            className="mt-10 inline-flex items-center gap-2 rounded-md bg-[--color-blue] px-8 py-4 text-[15px] font-medium text-white transition hover:-translate-y-0.5 hover:bg-[--color-blue-bright]"
          >
            <Search size={16} />
            Start Free Analysis
          </button>
          <div className="mt-4 text-[11px] font-mono text-[--color-muted]">
            No credit card required · 3 free scans · Results in seconds
          </div>
        </div>
      </motion.section>

      <motion.footer
        className="border-t border-[--color-border] px-6 py-12 md:px-12"
        variants={fadeUp}
        initial="initial"
        whileInView="animate"
        viewport={sectionViewport}
      >
        <div className="grid gap-10 md:grid-cols-6">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 text-[18px] font-extrabold text-white">
              <span className="text-[--color-blue]">◈</span>
              <span className="font-display">LEXTRACE</span>
            </div>
            <p className="mt-3 max-w-60 text-[13px] leading-[1.6] text-[--color-muted]">
              AI-powered content intelligence for the modern web.
            </p>
            <div className="mt-6 text-[11px] font-mono text-[--color-muted]">
              © 2026 LexTrace Inc.
            </div>
          </div>
          <div className="space-y-3 text-[12px] text-[--color-muted]">
            {['Features', 'Pricing', 'API', 'Changelog'].map((item) => (
              <div key={item} className="transition hover:text-white">
                {item}
              </div>
            ))}
          </div>
          <div className="space-y-3 text-[12px] text-[--color-muted]">
            {['Privacy', 'Terms', 'Security', 'Status'].map((item) => (
              <div key={item} className="transition hover:text-white">
                {item}
              </div>
            ))}
          </div>
        </div>
        <div className="mt-8 border-t border-[--color-border] pt-8 text-center text-[10px] font-mono uppercase tracking-[0.15em] text-[--color-muted]">
          Built with ◈ for content creators
        </div>
      </motion.footer>
    </div>
  )
}

function RiskBadge({ level }: { level: 'Low' | 'Medium' | 'High' | 'Critical' }) {
  const config = {
    Low: {
      bg: 'bg-green-500/15',
      text: 'text-green-400',
      border: 'border-green-500/30',
    },
    Medium: {
      bg: 'bg-yellow-500/15',
      text: 'text-yellow-400',
      border: 'border-yellow-500/30',
    },
    High: {
      bg: 'bg-orange-500/15',
      text: 'text-orange-400',
      border: 'border-orange-500/30',
    },
    Critical: {
      bg: 'bg-red-500/15',
      text: 'text-red-400',
      border: 'border-red-500/30',
    },
  }[level]

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.15em] ${config.bg} ${config.text} ${config.border}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.text.replace('text-', 'bg-')}`} />
      {level}
    </span>
  )
}

function ScanningBeam() {
  return (
    <motion.div
      className="pointer-events-none absolute left-0 right-0 h-px bg-linear-to-r from-transparent via-blue-600 to-transparent opacity-40"
      animate={{ top: ['0%', '100%'] }}
      transition={{ duration: 3.5, ease: 'linear', repeat: Infinity }}
    />
  )
}

export default App