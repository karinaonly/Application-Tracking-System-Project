import { useEffect, useMemo, useState } from "react"
import { Clipboard, Link, Briefcase, BarChart2, Plus, ExternalLink, Calendar, Building2, Loader2, ChevronDown, StickyNote } from "lucide-react"
import type { PageProps } from "../types"
import * as api from "../api"

const STATUS_ORDER: api.ApplicationStatus[] = ["saved", "applied", "interview", "offer", "rejected"]

const STATUS_META: Record<api.ApplicationStatus, { label: string; badge: string }> = {
  saved: { label: "Saved", badge: "bg-off text-mid border-edge" },
  applied: { label: "Applied", badge: "bg-[rgba(59,130,246,0.1)] text-[#2563EB] border-[rgba(59,130,246,0.25)]" },
  interview: { label: "Interview", badge: "bg-[rgba(245,158,11,0.12)] text-[#B45309] border-[rgba(245,158,11,0.3)]" },
  offer: { label: "Offer", badge: "bg-[rgba(0,201,167,0.1)] text-teal border-[rgba(0,201,167,0.3)]" },
  rejected: { label: "Rejected", badge: "bg-[rgba(255,71,87,0.08)] text-red border-[rgba(255,71,87,0.25)]" },
}

function statusOf(job: api.JobDescription): api.ApplicationStatus {
  return job.application_status ?? "saved"
}

function todayLocal(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

function ApplicationTracker({
  job,
  onUpdated,
  addToast,
}: {
  job: api.JobDescription
  onUpdated: (job: api.JobDescription) => void
  addToast: PageProps["addToast"]
}) {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<api.ApplicationStatus>(statusOf(job))
  const [appliedDate, setAppliedDate] = useState(job.applied_at ? job.applied_at.slice(0, 10) : "")
  const [notes, setNotes] = useState(job.notes ?? "")
  const [saving, setSaving] = useState(false)

  const currentStatus = statusOf(job)
  const currentDate = job.applied_at ? job.applied_at.slice(0, 10) : ""
  const currentNotes = job.notes ?? ""
  const dirty = status !== currentStatus || appliedDate !== currentDate || notes !== currentNotes

  const chooseStatus = (next: api.ApplicationStatus) => {
    setStatus(next)
    // Show the real "today" instead of silently inventing a past date. The
    // user can change or clear it before saving.
    if (next !== "saved" && !appliedDate) setAppliedDate(todayLocal())
  }

  const cancel = () => {
    setStatus(currentStatus)
    setAppliedDate(currentDate)
    setNotes(currentNotes)
    setOpen(false)
  }

  const save = async () => {
    setSaving(true)
    try {
      // Noon local time avoids a timezone shift changing the displayed day.
      const applied_at = appliedDate ? new Date(`${appliedDate}T12:00:00`).toISOString() : null
      const updated = await api.updateJobApplication(job.id, { status, applied_at, notes })
      onUpdated(updated)
      setOpen(false)
      addToast("success", "Application tracker updated.")
    } catch (error) {
      addToast("error", error instanceof Error ? error.message : "Could not update the application")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-3 pt-3 border-t border-edge">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {job.applied_at && (
          <span className="text-dim">Applied {new Date(job.applied_at).toLocaleDateString()}</span>
        )}
        {job.notes && (
          <span className="flex items-center gap-1 text-mid min-w-0">
            <StickyNote size={11} className="shrink-0" />
            <span className="truncate max-w-[24rem]">{job.notes}</span>
          </span>
        )}
        <button
          onClick={() => setOpen(!open)}
          className="ml-auto flex items-center gap-1 text-xs font-medium text-navy hover:text-teal transition-colors"
        >
          {open ? "Close tracker" : currentStatus === "saved" ? "Track application" : "Edit tracker"}
          <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      </div>

      {open && (
        <div className="mt-3 rounded-xl border border-edge bg-warm p-4 space-y-3">
          <div>
            <p className="text-xs font-medium text-navy mb-2">Status</p>
            <div className="flex flex-wrap gap-1.5">
              {STATUS_ORDER.map(value => (
                <button
                  key={value}
                  onClick={() => chooseStatus(value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    status === value
                      ? "bg-navy text-white border-navy"
                      : "bg-surface text-mid border-edge hover:border-navy/30"
                  }`}
                >
                  {STATUS_META[value].label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid sm:grid-cols-[180px_1fr] gap-3">
            <div>
              <label className="block text-xs font-medium text-navy mb-1.5">Applied date</label>
              <input
                type="date"
                value={appliedDate}
                max={todayLocal()}
                onChange={e => setAppliedDate(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-edge bg-surface text-sm text-navy outline-none focus:border-2 focus:border-navy transition-all"
              />
              <p className="text-[10px] text-dim mt-1">Optional — clear it if you have not applied.</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-navy mb-1.5">Notes</label>
              <textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                rows={2}
                maxLength={5000}
                placeholder="Recruiter name, interview stage, follow-up date…"
                className="w-full px-3 py-2 rounded-lg border border-edge bg-surface text-sm text-navy placeholder-dim outline-none focus:border-2 focus:border-navy transition-all resize-y"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[10px] text-dim">Only you can see this. Tracker notes are never sent to the AI provider.</p>
            <div className="flex items-center gap-2">
              <button
                onClick={cancel}
                className="px-3 py-1.5 text-xs font-medium text-mid hover:text-navy transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={save}
                disabled={saving || !dirty}
                className="px-4 py-1.5 bg-teal text-navy text-xs font-semibold rounded-lg hover:bg-teal-dim transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {saving ? "Saving…" : "Save tracker"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

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
  const [filter, setFilter] = useState<"all" | api.ApplicationStatus>("all")

  useEffect(() => {
    api.listJobs().then(setSavedJDs).catch(error => addToast("error", error.message))
  }, [addToast])

  const counts = useMemo(() => {
    const result: Record<api.ApplicationStatus, number> = { saved: 0, applied: 0, interview: 0, offer: 0, rejected: 0 }
    for (const job of savedJDs) result[statusOf(job)] += 1
    return result
  }, [savedJDs])

  const visibleJDs = filter === "all"
    ? savedJDs
    : savedJDs.filter(job => statusOf(job) === filter)

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

  const handleUpdated = (updated: api.JobDescription) => {
    setSavedJDs(current => current.map(job => job.id === updated.id ? updated : job))
  }

  const useForAnalysis = (job: api.JobDescription) => {
    api.saveSelectedJobId(job.id)
    addToast("info", `"${job.title}" will be preselected on the Upload page.`)
    navigate("upload")
  }

  return (
    <div className="min-h-screen bg-warm">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="font-display font-bold text-2xl text-navy mb-1">Job Descriptions</h1>
          <p className="text-mid text-sm">Save job postings to analyze your resume against, then track each application from saved to offer.</p>
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
                  <p className="text-xs text-dim">Works on public job pages. Sites that block automated access need a manual paste instead.</p>
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

        {/* Saved JDs + tracker */}
        <div>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h2 className="font-display font-semibold text-base text-navy">Saved Job Descriptions ({savedJDs.length})</h2>
            <div className="flex flex-wrap gap-1.5">
              {(["all", ...STATUS_ORDER] as const).map(value => {
                const count = value === "all" ? savedJDs.length : counts[value]
                const active = filter === value
                return (
                  <button
                    key={value}
                    onClick={() => setFilter(value)}
                    className={`px-2.5 py-1 rounded-full text-[11px] font-medium border transition-all ${
                      active
                        ? "bg-navy text-white border-navy"
                        : "bg-surface text-mid border-edge hover:border-navy/30"
                    }`}
                  >
                    {value === "all" ? "All" : STATUS_META[value].label}
                    <span className={`ml-1 ${active ? "text-white/60" : "text-dim"}`}>{count}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {savedJDs.length === 0 ? (
            <div className="bg-surface rounded-2xl border border-dashed border-edge p-10 text-center">
              <Briefcase size={22} className="text-dim mx-auto mb-2" />
              <p className="text-sm font-medium text-navy">No job descriptions saved yet</p>
              <p className="text-xs text-mid mt-1">Save one above to analyze your resume and start tracking the application.</p>
            </div>
          ) : visibleJDs.length === 0 ? (
            <div className="bg-surface rounded-2xl border border-dashed border-edge p-10 text-center">
              <p className="text-sm font-medium text-navy">No applications with this status</p>
              <p className="text-xs text-mid mt-1">Pick another filter or update a job's tracker.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {visibleJDs.map((jd) => {
                const status = statusOf(jd)
                return (
                  <div key={jd.id} className="bg-surface rounded-2xl border border-edge p-5 hover:border-navy/20 hover:shadow-sm transition-all group">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-start gap-3">
                        <div className="w-9 h-9 rounded-xl bg-off flex items-center justify-center shrink-0 mt-0.5">
                          <Briefcase size={16} className="text-mid" />
                        </div>
                        <div>
                          <p className="font-display font-semibold text-navy text-sm leading-tight">{jd.title}</p>
                          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                            <Building2 size={11} className="text-dim" />
                            <p className="text-xs text-mid">{jd.company || "Company not provided"}</p>
                            <span className="text-edge">·</span>
                            <Calendar size={11} className="text-dim" />
                            <p className="text-xs text-dim">{new Date(jd.created_at).toLocaleDateString()}</p>
                            <span className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 ${STATUS_META[status].badge}`}>
                              {STATUS_META[status].label}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => useForAnalysis(jd)}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-teal text-navy text-xs font-semibold rounded-lg hover:bg-teal-dim transition-all"
                        >
                          <BarChart2 size={12} />
                          Use for Analysis
                        </button>
                        {jd.url && (
                          <a
                            href={jd.url}
                            target="_blank"
                            rel="noreferrer"
                            className="p-1.5 rounded-lg text-dim hover:text-mid hover:bg-off transition-colors"
                            title="Open original posting"
                          >
                            <ExternalLink size={13} />
                          </a>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-mid line-clamp-2">{jd.raw_text}</p>
                    {jd.extracted_keywords && (jd.extracted_keywords.required_skills.length > 0 || jd.extracted_keywords.seniority !== "unspecified") && (
                      <div className="flex items-center gap-1.5 flex-wrap mt-3">
                        {jd.extracted_keywords.seniority !== "unspecified" && (
                          <span className="text-[10px] font-medium uppercase tracking-wide text-navy bg-off rounded-full px-2 py-0.5">
                            {jd.extracted_keywords.seniority}{jd.extracted_keywords.min_years_experience != null ? ` · ${jd.extracted_keywords.min_years_experience}+ yrs` : ""}
                          </span>
                        )}
                        {jd.extracted_keywords.required_skills.slice(0, 6).map(skill => (
                          <span key={skill} className="text-[10px] text-mid border border-edge rounded-full px-2 py-0.5">
                            {skill}
                          </span>
                        ))}
                        {jd.extracted_keywords.required_skills.length > 6 && (
                          <span className="text-[10px] text-dim">+{jd.extracted_keywords.required_skills.length - 6} more</span>
                        )}
                      </div>
                    )}
                    <ApplicationTracker job={jd} onUpdated={handleUpdated} addToast={addToast} />
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
