# LexTrace — Claude Code Generation Prompt

Build a complete, production-grade landing page + dashboard for **LexTrace**, an AI-powered content piracy detection platform. The result should look like a funded SaaS product — not a hackathon prototype.

---

## Project Setup

**Stack:** React 19 + Vite 6 + Tailwind CSS 4 + Motion (Framer Motion) + Lucide React + TypeScript

**package.json dependencies:**
- `react`, `react-dom` ^19.0.1
- `vite` ^6.2.3
- `@tailwindcss/vite` ^4.1.14, `tailwindcss` ^4.1.14
- `motion` ^12.23.24
- `lucide-react` ^0.546.0
- `@vitejs/plugin-react` ^5.0.4
- `typescript` ~5.8.2

**Fonts (loaded via Google Fonts in `index.css`):**
- Display: `Syne` (weights: 400, 600, 700, 800)
- Mono: `JetBrains Mono` (weights: 400, 500)
- Body: `DM Sans` (weights: 300, 400, 500)

```css
/* index.css */
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');
@import "tailwindcss";

@theme {
  --font-display: "Syne", ui-sans-serif, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
  --font-sans: "DM Sans", ui-sans-serif, system-ui, sans-serif;

  --color-bg: #05070f;
  --color-surface: #080c18;
  --color-border: rgba(255,255,255,0.06);
  --color-blue: #2563ff;
  --color-blue-bright: #3b82f6;
  --color-violet: #7c3aed;
  --color-cyan: #06b6d4;
  --color-text: #e8eaf0;
  --color-muted: #6b7280;
}

* { box-sizing: border-box; }

body {
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}

::selection {
  background: var(--color-blue);
  color: white;
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--color-bg); }
::-webkit-scrollbar-thumb { background: var(--color-blue); border-radius: 2px; }
```

**Global background:** `#05070f` (deep blue-black). Text: `#e8eaf0` (soft off-white). The entire page is dark.

---

## Color System

| Token | Value | Usage |
|---|---|---|
| `--color-bg` | `#05070f` | Page background |
| `--color-surface` | `#080c18` | Cards, panels |
| `--color-border` | `rgba(255,255,255,0.06)` | All borders |
| `--color-blue` | `#2563ff` | Primary CTA, key highlights |
| `--color-blue-bright` | `#3b82f6` | Hover states, links |
| `--color-violet` | `#7c3aed` | Secondary accent, gradients |
| `--color-cyan` | `#06b6d4` | Data highlights, scores |
| `--color-text` | `#e8eaf0` | Primary text |
| `--color-muted` | `#6b7280` | Labels, metadata |

**Gradient recipes used throughout:**
- Electric glow: `linear-gradient(135deg, #2563ff, #7c3aed)`
- Scan line: `linear-gradient(90deg, transparent, #2563ff40, transparent)`
- Card shimmer: `linear-gradient(135deg, rgba(37,99,255,0.08), rgba(124,58,237,0.05))`
- Mesh background: radial gradient blobs at corners, `#2563ff` at 5% opacity, `#7c3aed` at 3%

---

## Animation Variants

```tsx
const fadeUp = {
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] } }
};

const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.6, ease: "easeOut" } }
};

const staggerContainer = (delay = 0) => ({
  animate: { transition: { staggerChildren: 0.1, delayChildren: delay } }
});

const slideLeft = {
  initial: { opacity: 0, x: -20 },
  animate: { opacity: 1, x: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } }
};

const scaleIn = {
  initial: { opacity: 0, scale: 0.94 },
  animate: { opacity: 1, scale: 1, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } }
};
```

All `whileInView` animations use `viewport={{ once: true, margin: "-80px" }}`.

---

## STATE

```tsx
const [activeTab, setActiveTab] = useState<'analysis' | 'discovery' | 'dmca'>('analysis');
const [scanProgress, setScanProgress] = useState(0); // 0–100, drives the animated scan bar
const [showScanResult, setShowScanResult] = useState(false);
const [inputText, setInputText] = useState('');
const [isScanning, setIsScanning] = useState(false);

// Simulated scan: on "Analyze" click, setScanProgress increments via setInterval over 2200ms, then setShowScanResult(true)
```

---

## MOCK DATA

```tsx
const scanResults = {
  similarity: 94,
  confidence: 97,
  riskLevel: 'Critical',
  sourcesFound: 12,
  scanDuration: '2.3s',
  originalWords: 847,
  matchedWords: 797,
};

const sources = [
  { url: 'techcrunch-mirror.net', match: 97, type: 'Exact Copy', discovered: '2h ago', domain_authority: 42 },
  { url: 'content-farm-daily.com', match: 91, type: 'Near Duplicate', discovered: '5h ago', domain_authority: 18 },
  { url: 'newsaggregator.io', match: 84, type: 'Modified Copy', discovered: '1d ago', domain_authority: 31 },
  { url: 'mirror-posts.xyz', match: 79, type: 'Partial Copy', discovered: '2d ago', domain_authority: 9 },
  { url: 'repost-hub.co', match: 71, type: 'Partial Copy', discovered: '3d ago', domain_authority: 14 },
];
```

---

## FILE STRUCTURE

```
src/
  App.tsx              — entire app (all sections, all components)
  index.css            — global styles, CSS variables, fonts
  main.tsx             — entry point
```

Keep everything in `App.tsx` plus the `ScanningBeam` and `RiskBadge` helper components in the same file.

---

## SECTION 1: NAVBAR

Container: `fixed top-0 left-0 right-0 z-50`, `px-6 md:px-12 py-4`, `border-b border-[--color-border]`

**Background:** `backdrop-blur-xl bg-[rgba(5,7,15,0.8)]`

**Layout:** `flex items-center justify-between`

**Logo (left):**
- Wordmark `LEXTRACE` — `font-display font-800 text-[18px] tracking-[-0.02em] text-white`
- A small `◈` glyph before the wordmark in `text-[--color-blue]`
- Below: `text-[9px] font-mono tracking-[0.25em] uppercase text-[--color-muted]` — `"CONTENT INTELLIGENCE"`

**Nav links (center, hidden on mobile):**
`Features`, `How It Works`, `Dashboard`, `Pricing` — `text-[13px] text-[--color-muted] hover:text-white`, transition 200ms. Gap: `gap-8`.

**Right side:**
- `Sign In` — ghost text button, `text-[13px] text-[--color-muted] hover:text-white`
- `Start Free Trial` — primary button: `bg-[--color-blue] hover:bg-[--color-blue-bright] text-white text-[13px] font-medium px-4 py-2 rounded-md`, transition 200ms
- Mobile: hamburger icon (`Menu` from lucide, size 20)

**Entrance animation:** Slides down from `y: -20, opacity: 0` on mount, `delay: 0.1`.

---

## SECTION 2: HERO

Container: `relative w-full min-h-screen flex flex-col justify-center items-center text-center`, `pt-24 pb-16 px-6`

**Background effects (all `absolute`, `pointer-events-none`, `z-0`):**

1. Mesh gradient blobs:
   - Top-left blob: `w-[600px] h-[600px] rounded-full`, `background: radial-gradient(circle, rgba(37,99,255,0.12) 0%, transparent 70%)`, `-top-40 -left-40`
   - Top-right blob: same size, `rgba(124,58,237,0.08)`, `-top-20 -right-40`
   - Center glow: `w-[800px] h-[400px]`, `background: radial-gradient(ellipse, rgba(37,99,255,0.06) 0%, transparent 60%)`, `top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2`

2. Grid lines overlay:
   - SVG pattern: 1px horizontal and vertical lines, `rgba(255,255,255,0.03)`, grid size `60px × 60px`
   - Full viewport, `opacity-60`

3. Animated scan beam:
   - `absolute w-full h-[1px] bg-gradient-to-r from-transparent via-[--color-blue] to-transparent`
   - Animates `top` from `0%` to `100%` on a 4s loop, `ease: "linear"`, `repeat: Infinity`
   - `opacity-30`

**Top badge (above headline):**
- `inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[--color-blue]/30 bg-[--color-blue]/10 mb-6`
- Pulsing dot: `w-1.5 h-1.5 rounded-full bg-[--color-cyan]` with `scale` animation `[1, 1.4, 1]`, repeat Infinity, duration 2s
- Text: `text-[11px] font-mono tracking-[0.15em] uppercase text-[--color-cyan]` — `"AI-Powered Content Intelligence"`

**Main headline:**
```
TRACE
TRUTH
```
- Each word on its own line
- Font: `font-display font-800`
- Size: `text-[14vw] md:text-[11vw] lg:text-[10vw]` 
- `leading-[0.88] tracking-[-0.04em] text-white`
- Each word animates in with `letterBlock` variant (slides up, staggered 0.15s apart)
- Behind "TRUTH": a horizontal gradient underline, `h-[3px]`, `bg-gradient-to-r from-[--color-blue] via-[--color-violet] to-[--color-cyan]`, width `100%`, `mt-2`

**Subheadline:**
`"AI-powered content intelligence that discovers copied articles, unauthorized reposts, plagiarism, and digital piracy across the web."`
- `text-[15px] md:text-[17px] text-[--color-muted] leading-[1.65] max-w-[520px] mx-auto mt-8 mb-10`
- Animates with `fadeUp`, `delay: 0.5`

**CTA Buttons (row, `gap-4`, `flex-wrap justify-center`):**

Primary — `"Analyze Content"`:
- `bg-[--color-blue] hover:bg-[--color-blue-bright] text-white px-6 py-3 rounded-md text-[14px] font-medium`
- Left icon: `Search` from lucide, size 16
- Hover: `translateY(-1px)` + `shadow-[0_8px_30px_rgba(37,99,255,0.4)]`
- Transition: 200ms

Secondary — `"View Demo"`:
- `border border-[--color-border] hover:border-white/20 text-[--color-muted] hover:text-white px-6 py-3 rounded-md text-[14px]`
- Left icon: `Play` from lucide, size 16
- Hover: `translateY(-1px)`

**Stat row (below buttons, `mt-16 gap-8 md:gap-16`, `flex-wrap justify-center`):**
Three stats:
- `"2.4B+"` / `"Web pages scanned"`
- `"99.2%"` / `"Detection accuracy"`
- `"< 3s"` / `"Analysis time"`

Each stat: number in `text-[28px] font-display font-700 text-white`, label in `text-[11px] font-mono tracking-[0.15em] uppercase text-[--color-muted]`. Vertical divider `w-[1px] h-12 bg-[--color-border]` between them (hidden on mobile).

**Hero Dashboard Preview (below stats, `mt-20`, `z-10 relative`):**

A floating mock dashboard card:
- `max-w-[860px] mx-auto rounded-xl border border-[--color-border] overflow-hidden`
- `background: linear-gradient(135deg, rgba(8,12,24,0.9), rgba(5,7,15,0.95))`
- `box-shadow: 0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(37,99,255,0.1), inset 0 1px 0 rgba(255,255,255,0.04)`
- Subtle top edge glow: `absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-[--color-blue]/50 to-transparent`

Inside the card — **mock scan interface:**

Top bar (card header): `px-5 py-3 border-b border-[--color-border] flex items-center gap-3`
- Three dots: `w-3 h-3 rounded-full`, colors `#ff5f57`, `#ffbd2e`, `#28c840`
- Center: `text-[11px] font-mono text-[--color-muted] tracking-[0.1em]` — `"lextrace.io/analyze"`
- Right: small `Shield` icon from lucide in `text-[--color-cyan]`, size 14

Main card body: `grid grid-cols-3 gap-0`

Left column (col-span-2): Text input area mockup
- `p-5 border-r border-[--color-border]`
- Label: `text-[10px] font-mono uppercase tracking-[0.2em] text-[--color-muted] mb-3`
- Fake text lines: divs with `h-2 rounded-full bg-white/10 mb-2`, varying widths (`w-full`, `w-5/6`, `w-4/5`, `w-full`, `w-3/4`, `w-5/6`)
- A highlighted "selected" region: two lines with `bg-[--color-blue]/20 border-l-2 border-[--color-blue]` to simulate text selection
- Below: `"Analyze Content"` button in miniature — `w-full mt-4 py-2 bg-[--color-blue] rounded text-[11px] font-mono text-white text-center`

Right column: Metrics preview
- `p-5 space-y-4`
- Similarity score ring (SVG circle): `cx=40 cy=40 r=32`, stroke-dasharray based on `94%`, animated `strokeDashoffset` from full to partial on mount, `stroke: #2563ff`, `strokeWidth: 3`, `fill: none`. Center text: `94%` in `text-[16px] font-display font-700 text-white`, `text-[9px] font-mono text-[--color-muted]` below.
- Risk badge: `"CRITICAL"` in `text-[9px] font-mono tracking-[0.15em] uppercase`, `bg-red-500/15 text-red-400 border border-red-500/30 px-2 py-1 rounded-full`
- Sources found: `"12"` in `text-[20px] font-display font-700 text-[--color-cyan]`, `"Sources Detected"` in `text-[9px] font-mono text-[--color-muted]`

The whole card animates: `scaleIn` variant, `delay: 0.8`. Has `whileHover={{ y: -4 }}` with `shadow-[0_60px_120px_rgba(0,0,0,0.8)]`.

---

## SECTION 3: FEATURES

Container: `relative w-full py-32 px-6 md:px-12`, `z-20`

**Section label:** `[ 01 ] Core Features` — `text-[10px] font-mono tracking-[0.25em] uppercase text-[--color-blue] mb-4`

**Heading:**
`"Everything you need to protect your content"` — `font-display font-700 text-[2.4rem] md:text-[3.2rem] leading-[1.1] tracking-[-0.03em] text-white max-w-[600px] mb-4`

**Sub-heading:** `text-[15px] text-[--color-muted] max-w-[480px] mb-16`

**Feature cards grid:** `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4`

Six cards. Each card:
- `rounded-xl border border-[--color-border] p-6`
- `background: linear-gradient(135deg, rgba(8,12,24,0.8), rgba(5,7,15,0.6))`
- Hover: `border-[--color-blue]/30` + `background` shifts to include more blue tint + `translateY(-2px)`
- Transition: 300ms

**Card internal structure:**
- Top: Icon container `w-10 h-10 rounded-lg flex items-center justify-center mb-5`, `background: linear-gradient(135deg, rgba(37,99,255,0.2), rgba(124,58,237,0.1))`, `border border-[--color-blue]/20`. Icon from lucide, size 18, `text-[--color-blue]`.
- Title: `text-[15px] font-display font-600 text-white mb-2`
- Description: `text-[13px] text-[--color-muted] leading-[1.6]`
- Bottom tag: `text-[10px] font-mono tracking-[0.15em] uppercase text-[--color-blue]/60 mt-4`

**Six features:**

1. Icon: `ScanSearch` / Title: `"Similarity Analysis"` / Desc: `"AI calculates exact similarity percentages, match confidence, and content overlap across billions of web pages."` / Tag: `"AI-POWERED"`

2. Icon: `Globe` / Title: `"Source Discovery"` / Desc: `"Scans the web to find every site that published your content — exact copies, near-duplicates, and modified reposts."` / Tag: `"WEB-SCALE"`

3. Icon: `FileText` / Title: `"Evidence Reports"` / Desc: `"Generate professional PDF reports with matched excerpts, screenshots, timestamps, and legal-grade evidence packages."` / Tag: `"EXPORT READY"`

4. Icon: `Mail` / Title: `"DMCA Actions"` / Desc: `"Prepare takedown-ready notices instantly, copy legal text, and open top matched sources to file requests quickly."` / Tag: `"TAKEDOWN READY"`

5. Icon: `ShieldAlert` / Title: `"Risk Scoring"` / Desc: `"AI assigns Low / Medium / High / Critical risk levels based on similarity, domain authority, and copy depth."` / Tag: `"RISK INTEL"`

6. Icon: `Bell` / Title: `"Monitoring"` / Desc: `"Track your content over time. Get alerts when new copies appear, sources change, or repeat offenders strike again."` / Tag: `"REAL-TIME"`

Cards stagger in with `whileInView` + `staggerChildren: 0.08`.

**Large feature callout (below grid, `mt-8`):**
Full-width card: `rounded-xl border border-[--color-border] p-8 md:p-12`, same surface background.
- Left: `"Powered by semantic AI — not just keyword matching"` in `font-display font-700 text-[1.6rem] md:text-[2.2rem] text-white leading-[1.2]`
- Right: paragraph of description + a `"Learn More →"` link in `text-[--color-blue]`
- Background: faint radial glow `rgba(37,99,255,0.05)` at center

---

## SECTION 4: HOW IT WORKS

Container: `relative w-full py-32 px-6 md:px-12 bg-[--color-surface]`, top and bottom `border-y border-[--color-border]`

**Section label:** `[ 02 ] How It Works`

**Heading:** `"From paste to proof in seconds"` — same display style as Section 3

**Steps:** Horizontal timeline on desktop (`flex items-start gap-0`), vertical stack on mobile. Four steps connected by a dashed line `border-t border-dashed border-[--color-border]` that runs through their midpoints.

Each step:
- Number: `text-[10px] font-mono tracking-[0.2em] uppercase text-[--color-blue] mb-3` — `"STEP 01"`
- Icon circle: `w-12 h-12 rounded-full border border-[--color-blue]/30 bg-[--color-blue]/10 flex items-center justify-center mb-4`. Icon from lucide, `text-[--color-blue]`, size 20.
- Title: `text-[16px] font-display font-600 text-white mb-2`
- Desc: `text-[13px] text-[--color-muted] leading-[1.6] max-w-[220px]`

Steps:
1. `Upload` icon / `"Submit Content"` / `"Paste text, enter a URL, or upload a document"`
2. `Radar` icon / `"Scan the Web"` / `"LexTrace searches billions of pages for matches"`
3. `Cpu` icon / `"AI Analysis"` / `"Semantic AI calculates similarity and risk scores"`
4. `FileCheck` icon / `"Get Evidence"` / `"Download your full report with legal-grade evidence"`

---

## SECTION 5: INTERACTIVE DEMO (Dashboard Preview)

Container: `relative w-full py-32 px-6 md:px-12`

**Section label:** `[ 03 ] Live Dashboard`

**Heading:** `"See LexTrace in action"`

**Dashboard container:** `mt-12 rounded-xl border border-[--color-border] overflow-hidden`, `background: var(--color-surface)`, max-width 1100px, centered.

**Dashboard top bar:**
- `px-6 py-3 border-b border-[--color-border] flex items-center justify-between`
- Left: Tab row — three tabs: `"New Scan"`, `"Results"`, `"DMCA Actions"`. Active: `text-white border-b-2 border-[--color-blue]`. Inactive: `text-[--color-muted] hover:text-white`. `text-[12px] font-mono tracking-[0.1em] pb-3 gap-6`.
- Right: `"New Scan"` button — miniature CTA

**TAB: Similarity Analysis** (`activeTab === 'analysis'`)

Two-column layout (`grid grid-cols-5 gap-0`):

Left column (col-span-3): Input area
- Label: `"CONTENT INPUT"` in mono label style
- Mock article text area: `min-h-[200px] p-4 rounded-lg border border-[--color-border] bg-[rgba(255,255,255,0.02)] text-[13px] text-[--color-muted] leading-[1.7] font-mono`. Show a placeholder article paragraph.
- Below: scan button — on click triggers `isScanning = true`, progress bar animates 0→100% over 2200ms, then `showScanResult = true`.
- `Analyze Now` button with `ScanSearch` icon. During scanning: pulsing state, text changes to `"Scanning..."`, button becomes `opacity-70 cursor-not-allowed`.
- Scan progress bar: `h-[2px] bg-[--color-border] rounded-full overflow-hidden`, inner bar `bg-gradient-to-r from-[--color-blue] to-[--color-cyan]`, width = `${scanProgress}%`.

Right column (col-span-2): Results panel
- Shows placeholder state if `!showScanResult`: centered icon + `"Run an analysis to see results"` in `text-[--color-muted]`
- Once `showScanResult`:
  - Similarity ring (SVG, same as hero card but larger: `cx=60 cy=60 r=50`, strokeWidth 4)
  - `"94% Similarity"` — `text-[28px] font-display font-700 text-white`
  - Risk badge: `RiskBadge` component (see below)
  - Row of three mini-stats: Confidence, Sources, Words Matched
  - AI Insight box: `bg-[--color-blue]/10 border border-[--color-blue]/20 rounded-lg p-4 mt-4`, `ShieldAlert` icon + text `"High probability of content theft detected. 12 sources indexed this article within 48 hours of publication."` in `text-[12px] text-[--color-blue-bright] leading-[1.6]`

All results animate in with `AnimatePresence` + `scaleIn`.

**TAB: Results** (`activeTab === 'discovery'`)

Table of discovered sources:

Header row: `"Source"` / `"Match %"` / `"Type"` / `"Discovered"` / `"DA"` — `text-[10px] font-mono tracking-[0.15em] uppercase text-[--color-muted] border-b border-[--color-border] pb-3`

Each source row:
- `border-b border-[--color-border] py-4 flex items-center`
- URL: `Globe` icon (size 14) + `text-[13px] font-mono text-white`
- Match %: colored number — `>90%` = `text-red-400`, `80-90%` = `text-orange-400`, `<80%` = `text-yellow-400`
- Type badge: small pill, `text-[10px] font-mono` — `"Exact Copy"` = red tint, `"Near Duplicate"` = orange tint, `"Modified Copy"` = yellow tint, `"Partial Copy"` = gray tint
- Discovered: `text-[12px] text-[--color-muted]`
- DA number: `text-[12px] font-mono text-[--color-muted]`
- Hover: row gets `bg-white/[0.02]`
- Row staggered entrance: `staggerChildren: 0.06`

Below table: `"View All 12 Sources →"` link

**TAB: DMCA Actions** (`activeTab === 'dmca'`)

DMCA action panel:
- Show backend-generated DMCA notice (preformatted text block) when available.
- Primary action: `"Copy Notice"` button to copy the generated notice to clipboard.
- Secondary action: `"Open Top Matched Source"` link to open the strongest offending URL in a new tab.
- Empty state text: `"Run a new scan to prepare DMCA actions."`

---

## HELPER COMPONENTS

### RiskBadge

```tsx
function RiskBadge({ level }: { level: 'Low' | 'Medium' | 'High' | 'Critical' }) {
  const config = {
    Low: { bg: 'bg-green-500/15', text: 'text-green-400', border: 'border-green-500/30' },
    Medium: { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30' },
    High: { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30' },
    Critical: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30' },
  }[level];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[10px] font-mono tracking-[0.15em] uppercase ${config.bg} ${config.text} ${config.border}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.text.replace('text-', 'bg-')}`} />
      {level}
    </span>
  );
}
```

### ScanningBeam

```tsx
function ScanningBeam() {
  return (
    <motion.div
      className="absolute left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-[#2563ff] to-transparent opacity-40 pointer-events-none"
      animate={{ top: ['0%', '100%'] }}
      transition={{ duration: 3.5, ease: 'linear', repeat: Infinity }}
    />
  );
}
```

---

## SECTION 6: SOCIAL PROOF

Container: `py-24 px-6 md:px-12 border-y border-[--color-border]`

**Label:** `"TRUSTED BY CONTENT TEAMS WORLDWIDE"` — `text-[10px] font-mono tracking-[0.25em] uppercase text-[--color-muted] text-center mb-12`

**Logo row:** `flex flex-wrap justify-center items-center gap-10 md:gap-16 opacity-40`
Five fake company names in `font-display font-700 text-[18px] text-[--color-muted]`:
`"NEXUS MEDIA"` / `"VERITAS POST"` / `"ATLAS DIGITAL"` / `"KRONOS WIRE"` / `"SENTINEL INK"`

---

## SECTION 7: FINAL CTA

Container: `relative py-40 px-6 md:px-12 text-center overflow-hidden`

Background: Large centered radial gradient — `radial-gradient(ellipse 80% 50% at 50% 50%, rgba(37,99,255,0.12), transparent)`

**Badge:** Same pulsing badge style as hero: `"START PROTECTING YOUR CONTENT"`

**Headline:**
```
Protect Your Content
Before It Spreads.
```
`font-display font-800 text-[3rem] md:text-[5rem] leading-[1.05] tracking-[-0.04em] text-white`

**Sub:** `text-[16px] text-[--color-muted] max-w-[400px] mx-auto mt-6 mb-10`

**CTA Button:** Large version — `px-8 py-4 text-[15px]`, same styling as hero primary CTA. `Search` icon + `"Start Free Analysis"`

**Below button:** `text-[11px] font-mono text-[--color-muted] mt-4` — `"No credit card required · 3 free scans · Results in seconds"`

---

## SECTION 8: FOOTER

`border-t border-[--color-border] px-6 md:px-12 py-12`

Three columns:

**Left (col-span-2):**
- Logo wordmark (same as navbar)
- `"AI-powered content intelligence for the modern web."` — `text-[13px] text-[--color-muted] mt-3 max-w-[240px] leading-[1.6]`
- `"© 2026 LexTrace Inc."` — `text-[11px] font-mono text-[--color-muted] mt-6`

**Center:** Links — `"Features"`, `"Pricing"`, `"API"`, `"Changelog"` — `text-[12px] text-[--color-muted] hover:text-white gap-3`

**Right:** Links — `"Privacy"`, `"Terms"`, `"Security"`, `"Status"` — same style

Bottom row: `"Built with ◈ for content creators"` in `text-[10px] font-mono text-[--color-muted] tracking-[0.15em]` — centered, `mt-8 pt-8 border-t border-[--color-border]`

---

## QUALITY REQUIREMENTS

1. **No placeholder lorem ipsum anywhere** — all copy must be real, specific, and product-relevant
2. **All animations use `motion` from `motion/react`** — no CSS keyframes except the scrollbar
3. **Tailwind v4 syntax** — use `@theme` variables in CSS, reference them as `[--color-blue]` in class names
4. **No `<form>` tags** — use `onClick`/`onChange` event handlers
5. **The scan interaction must work** — clicking Analyze should trigger the full 2200ms progress animation, then reveal results
6. **Tab switching must work** — all four dashboard tabs must render their respective content
7. **Mobile responsive** — all sections must look good at 375px width; nav collapses to hamburger
8. **TypeScript strict** — all props typed, no `any`
9. **Single file** — entire app in `App.tsx`, helpers at the bottom
10. **`whileInView` on all major sections** — nothing should be visible until scrolled into view (except hero)

---

## VISUAL MOOD REFERENCE

The finished product should evoke: a tool that security professionals and serious media organizations would trust. Think Datadog meets Linear meets Vercel. Dark, precise, data-dense but not cluttered. Every element earns its place.

**NOT:** a startup landing page with gradients and emojis.
**YES:** an enterprise SaaS tool that makes content piracy feel like a solved problem.