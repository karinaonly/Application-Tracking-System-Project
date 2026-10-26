import { useEffect, useState } from "react"
import { Clipboard, Link, Briefcase, Trash2, BarChart2, Plus, ExternalLink, Calendar, Building2, Loader2 } from "lucide-react"
import type { PageProps } from "../types"
import * as api from "../api"

const demoSavedJDs = [
  {
    title: "Senior Software Engineer",
    company: "Stripe",
    date: "Sep 22, 2026",
    keywords: ["Python", "distributed systems", "payment systems", "Kubernetes", "gRPC", "Kafka"],
    url: "https://stripe.com/jobs/listing/senior-swe",
  },
  {
    title: "Staff Engineer",
    company: "Vercel",
    date: "Sep 17, 2026",
    keywords: ["Next.js", "edge computing", "React", "TypeScript", "Rust", "CDN"],
    url: "https://vercel.com/careers/staff-engineer",
  },
  {
    title: "Platform Engineer",
    company: "Linear",
    date: "Sep 9, 2026",
    keywords: ["Kubernetes", "Terraform", "AWS", "observability", "SRE", "Go"],
    url: null,
  },
]

export default function JobDescriptions({ navigate, addToast }: PageProps) {
  const [tab, setTab] = useState<"paste" | "url">("paste")
  const [title, setTitle] = useState("")
  const [company, setCompany] = useState("")
  const [body, setBody] = useState("")
  const [url, setUrl] = useState("")
  const [scraping, setScraping] = useState(false)
  const [scraped, setScraped] = useState(false)
  const [charCount, setCharCount] = useState(0)
  const [savedJDs, setSavedJDs] = useState<api.JobDescription[]>([])

  useEffect(() => {
    api.listJobs().then(setSavedJDs).catch(error => addToast("error", error.message))
  }, [addToast])

  const handleScrape = async () => {
    if (!url.startsWith("http")) { addToast("error", "Please enter a valid URL starting with https://"); return }
    setScraping(true)
    try {
      const job = await api.scrapeJob(url)
      setTitle(job.title); setCompany(job.company ?? ""); setBody(job.raw_text)
      setCharCount(job.raw_text.length); setScraped(true); setTab("paste")
      addToast("success", "Job description scraped successfully!")
    } catch (error) { addToast("error", error instanceof Error ? error.message : "Could not scrape job") }
    finally { setScraping(false) }
  }

  const handleSave = async () => {
    if (!title.trim()) { addToast("error", "Please enter a job title"); return }
    if (body.trim().length < 50) { addToast("error", "Please paste a complete job description (min. 50 characters)"); return }
    try {
      const job = await api.createJob({ title, company: company || undefined, raw_text: body, url: url || undefined })
      setSavedJDs(current => [job, ...current])
      addToast("success", `"${title}" saved to your job descriptions!`)
      setTitle(""); setCompany(""); setBody(""); setUrl(""); setCharCount(0); setScraped(false)
    } catch (error) { addToast("error", error instanceof Error ? error.message : "Could not save job") }
  }

  return (
    <div className="min-h-screen bg-warm">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="font-display font-bold text-2xl text-navy mb-1">Job Descriptions</h1>
          <p className="text-mid text-sm">Save job postings to analyze your resume against. Paste manually or import from a URL.</p>
        </div>

        {/* Input card */}
        <div className="bg-surface rounded-2xl border border-edge overflow-hidden mb-8">
          {/* Tabs */}
          <div className="flex border-b border-edge">
            {([["paste", Clipboard, "Paste Manually"], ["url", Link, "Import from URL"]] as const).map(([id, Icon, label]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`flex items-center gap-2 px-6 py-4 text-sm font-medium transition-all border-b-2 -mb-px ${
                  tab === id ? "border-teal text-teal" : "border-transparent text-mid hover:text-navy"
                }`}
              >
                <Icon size={15} />
                {label}
              </button>
            ))}
          </div>

          <div className="p-6">
            {tab === "url" ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-navy mb-1.5">Job Posting URL</label>
                  <div className="flex gap-3">
                    <div className="relative flex-1">
                      <Link size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-dim" />
                      <input
                        type="url"
                        value={url}
                        onChange={e => setUrl(e.target.value)}
                        placeholder="https://company.com/jobs/senior-engineer"
                        className="w-full pl-9 pr-4 py-3 rounded-xl border border-edge bg-warm text-sm text-navy placeholder-dim outline-none focus:border-2 focus:border-navy transition-all"
                      />
                    </div>
                    <button
                      onClick={handleScrape}
                      disabled={scraping || !url}
                      className="flex items-center gap-2 px-5 py-3 bg-navy text-white text-sm font-semibold rounded-xl hover:bg-navy-light transition-all disabled:opacity-50 shrink-0"
                    >
                      {scraping ? <><Loader2 size={14} className="animate-spin" /> Scraping…</> : <><ExternalLink size={14} /> Scrape & Import</>}
                    </button>
                  </div>
                </div>
                {scraping && (
                  <div className="flex items-center gap-3 p-4 rounded-xl bg-off">
                    <Loader2 size={16} className="animate-spin text-teal" />
                    <div>
                      <p className="text-sm font-medium text-navy">Scraping job page…</p>
                      <p className="text-xs text-mid">Extracting title, company, and job description</p>
                    </div>
                  </div>
                )}
                {!scraping && (
                  <p className="text-xs text-dim">Supports LinkedIn, Greenhouse, Lever, Workday, Indeed, and most job boards.</p>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {scraped && (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-teal/5 border border-teal/20">
                    <div className="w-4 h-4 rounded-full bg-teal flex items-center justify-center shrink-0">
                      <span className="text-white text-[8px] font-bold">✓</span>
                    </div>
                    <p className="text-sm font-medium text-teal">Job description imported from URL — review and save below</p>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-navy mb-1.5">Job Title <span className="text-red">*</span></label>
                    <input
                      value={title}
                      onChange={e => setTitle(e.target.value)}
                      placeholder="Senior Software Engineer"
                      className="w-full px-4 py-3 rounded-xl border border-edge bg-warm text-sm text-navy placeholder-dim outline-none focus:border-2 focus:border-navy transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-navy mb-1.5">Company <span className="text-dim text-xs font-normal">(optional)</span></label>
                    <input
                      value={company}
                      onChange={e => setCompany(e.target.value)}
                      placeholder="Stripe"
                      className="w-full px-4 py-3 rounded-xl border border-edge bg-warm text-sm text-navy placeholder-dim outline-none focus:border-2 focus:border-navy transition-all"
                    />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-sm font-medium text-navy">Job Description <span className="text-red">*</span></label>
                    <span className="text-xs text-dim font-code">{charCount} chars</span>
                  </div>
                  <textarea
                    value={body}
                    onChange={e => { setBody(e.target.value); setCharCount(e.target.value.length) }}
                    placeholder="Paste the full job description here — include requirements, responsibilities, and qualifications for the most accurate keyword analysis…"
                    rows={8}
                    className="w-full px-4 py-3 rounded-xl border border-edge bg-warm text-sm text-navy placeholder-dim outline-none focus:border-2 focus:border-navy transition-all resize-y min-h-[160px]"
                  />
                  <p className="text-xs text-dim mt-1.5">Paste the complete job description for best keyword match accuracy (min. 200 chars recommended)</p>
                </div>
                <div className="flex items-center justify-between pt-2">
                  <button
                    onClick={() => { setTitle(""); setCompany(""); setBody(""); setCharCount(0); setScraped(false) }}
                    className="text-sm text-dim hover:text-mid transition-colors"
                  >
                    Clear
                  </button>
                  <button
                    onClick={handleSave}
                    className="flex items-center gap-2 px-5 py-2.5 bg-teal text-navy text-sm font-semibold rounded-xl hover:bg-teal-dim transition-all"
                    style={{ boxShadow: "0 2px 12px rgba(0,201,167,0.25)" }}
                  >
                    <Plus size={15} />
                    Save Job Description
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Saved JDs */}
        <div>
          <h2 className="font-display font-semibold text-base text-navy mb-4">Saved Job Descriptions ({savedJDs.length})</h2>
          <div className="space-y-3">
            {savedJDs.map((jd) => (
              <div key={jd.id} className="bg-surface rounded-2xl border border-edge p-5 hover:border-navy/20 hover:shadow-sm transition-all group">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-xl bg-off flex items-center justify-center shrink-0 mt-0.5">
                      <Briefcase size={16} className="text-mid" />
                    </div>
                    <div>
                      <p className="font-display font-semibold text-navy text-sm leading-tight">{jd.title}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <Building2 size={11} className="text-dim" />
                        <p className="text-xs text-mid">{jd.company || "Company not provided"}</p>
                        <span className="text-edge">·</span>
                        <Calendar size={11} className="text-dim" />
                        <p className="text-xs text-dim">{new Date(jd.created_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => { addToast("info", `Analyzing against "${jd.title}"…`); navigate("upload") }}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-teal text-navy text-xs font-semibold rounded-lg hover:bg-teal-dim transition-all"
                    >
                      <BarChart2 size={12} />
                      Use for Analysis
                    </button>
                    {jd.url && (
                      <button
                        className="p-1.5 rounded-lg text-dim hover:text-mid hover:bg-off transition-colors"
                        title="Open original posting"
                      >
                        <ExternalLink size={13} />
                      </button>
                    )}
                    <button
                      onClick={() => addToast("info", "Job deletion is not available in the backend yet.")}
                      className="p-1.5 rounded-lg text-dim hover:text-red hover:bg-red/10 transition-colors"
                      title="Delete"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
                <p className="text-xs text-mid line-clamp-2">{jd.raw_text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
