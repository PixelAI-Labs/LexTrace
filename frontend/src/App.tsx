import { useMemo, useState } from 'react'

type CandidateArticle = {
  rank: number
  url: string
  domain: string
  title: string | null
  rank_score: number
  keyword_coverage: number
  content_preview: string
  text_length: number
  publish_date: string | null
  language: string | null
}

type DiscoveryResponse = {
  request_id: string
  status: 'completed' | 'partial' | 'failed'
  original_title: string | null
  queries_used: string[]
  total_urls_collected: number
  candidates: CandidateArticle[]
  metadata: {
    total_candidates: number
    queries_generated: number
    extraction_time_ms: number
    search_time_ms: number
    total_time_ms: number
  }
}

function App() {
  const [title, setTitle] = useState('')
  const [articleText, setArticleText] = useState('')
  const [response, setResponse] = useState<DiscoveryResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const canSubmit = useMemo(
    () => articleText.trim().length >= 100 && !isLoading,
    [articleText, isLoading],
  )

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canSubmit) {
      return
    }

    setIsLoading(true)
    setError(null)
    setResponse(null)

    try {
      const payload = {
        article_text: articleText,
        title: title.trim() ? title.trim() : null,
        options: {
          max_candidates: 20,
          search_depth: 'shallow',
          include_content: true,
        },
      }

      const res = await fetch('/api/v1/discover', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        const message = detail?.detail ?? `Request failed with status ${res.status}`
        throw new Error(message)
      }

      const data = (await res.json()) as DiscoveryResponse
      setResponse(data)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unexpected error occurred.'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10 text-slate-900">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-8">
        <header className="space-y-2">
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Discovery Service
          </p>
          <h1 className="text-3xl font-semibold text-slate-900">
            Article Discovery
          </h1>
          <p className="text-sm text-slate-600">
            Submit an article to discover possible copies and view extracted candidates.
          </p>
        </header>

        <form
          onSubmit={handleSubmit}
          className="space-y-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
        >
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="title">
              Optional title
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Article title"
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-slate-400 focus:outline-none"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="article-text">
              Article text
            </label>
            <textarea
              id="article-text"
              value={articleText}
              onChange={(event) => setArticleText(event.target.value)}
              placeholder="Paste the article content here (minimum 100 characters)."
              className="min-h-[220px] w-full resize-y rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-slate-400 focus:outline-none"
            />
            <p className="text-xs text-slate-500">
              {articleText.trim().length} characters
            </p>
          </div>

          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex items-center justify-center rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isLoading ? 'Discovering...' : 'Discover'}
          </button>
        </form>

        {isLoading && (
          <div className="rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-600">
            Searching and extracting candidates. This may take a moment.
          </div>
        )}

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {response && (
          <section className="space-y-6">
            <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">Results</h2>
              <div className="mt-4 grid gap-4 text-sm text-slate-600 sm:grid-cols-3">
                <div>
                  <p className="text-xs uppercase text-slate-400">Queries used</p>
                  <p className="text-base font-semibold text-slate-900">
                    {response.queries_used.length}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-400">Total URLs collected</p>
                  <p className="text-base font-semibold text-slate-900">
                    {response.total_urls_collected}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-400">Candidate count</p>
                  <p className="text-base font-semibold text-slate-900">
                    {response.candidates.length}
                  </p>
                </div>
              </div>

              {response.queries_used.length > 0 && (
                <div className="mt-6">
                  <p className="text-xs uppercase text-slate-400">Queries used</p>
                  <ul className="mt-2 space-y-1 text-sm text-slate-700">
                    {response.queries_used.map((query) => (
                      <li key={query} className="rounded bg-slate-100 px-2 py-1">
                        {query}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="space-y-4">
              {response.candidates.map((candidate) => (
                <article
                  key={candidate.url}
                  className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h3 className="text-base font-semibold text-slate-900">
                        {candidate.title || 'Untitled result'}
                      </h3>
                      <p className="text-xs text-slate-500">{candidate.domain}</p>
                    </div>
                    <a
                      href={candidate.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-semibold text-slate-600 hover:text-slate-900"
                    >
                      Open
                    </a>
                  </div>

                  <p className="mt-3 text-sm text-slate-700">
                    {candidate.content_preview}
                  </p>

                  <div className="mt-4 text-xs text-slate-500">
                    Text length: {candidate.text_length}
                  </div>
                </article>
              ))}

              {response.candidates.length === 0 && (
                <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">
                  No candidates returned for this article.
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

export default App
