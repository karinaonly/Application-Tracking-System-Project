import { useEffect, useState } from "react"
import {
  AlertTriangle,
  Check,
  Copy,
  Download,
  FileText,
  Loader2,
  Shield,
  Sparkles,
} from "lucide-react"
import type { PageProps } from "../types"
import * as api from "../api"

const TONES: Array<{ value: api.CoverLetterTone; label: string; hint: string }> = [
  { value: "professional", label: "Professional", hint: "Direct and calm" },
  { value: "enthusiastic", label: "Enthusiastic", hint: "Warm, still factual" },
  { value: "concise", label: "Concise", hint: "Under 250 words" },
]

export default function CoverLetterCard({
  resumeId,
  jobId,
  addToast,
}: {
  resumeId: string
  jobId: string
  addToast: PageProps["addToast"]
}) {
  const [preview, setPreview] = useState<api.CoverLetterPreview | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(true)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [tone, setTone] = useState<api.CoverLetterTone>("professional")
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<api.CoverLetterResult | null>(null)
  const [text, setText] = useState("")
  const [copied, setCopied] = useState(false)
  const aiPreference = api.getAiRewritingPreference()

  useEffect(() => {
    let cancelled = false
    setLoadingPreview(true)
    setPreviewError(null)
    setResult(null)
    setText("")
    api.getCoverLetterPreview(resumeId, jobId)
      .then(data => { if (!cancelled) setPreview(data) })
      .catch(error => {
        if (!cancelled) {
          setPreviewError(error instanceof Error ? error.message : "Could not load the cover-letter source")
        }
      })
      .finally(() => { if (!cancelled) setLoadingPreview(false) })
    return () => { cancelled = true }
  }, [resumeId, jobId])

  const source = preview?.source
  const serverAvailable = preview?.available ?? false
  const available = serverAvailable && aiPreference

  const generate = async () => {
    setGenerating(true)
    try {
      const generated = await api.generateCoverLetter({ resume_id: resumeId, job_id: jobId, tone })
      setResult(generated)
      setText(generated.text)
      if (generated.guard.status === "flagged") {
        addToast("info", "The draft was flagged for review. Check the warnings before you use it.")
      } else {
        addToast("success", "Cover letter generated. Review and edit it before sending.")
      }
    } catch (error) {
      addToast("error", error instanceof Error ? error.message : "Could not generate a cover letter")
    } finally {
      setGenerating(false)
    }
  }

  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const download = () => {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" })
    const link = document.createElement("a")
    link.href = URL.createObjectURL(blob)
    link.download = "Cover_Letter.txt"
    link.click()
    URL.revokeObjectURL(link.href)
  }

  const unavailableMessage = !serverAvailable
    ? preview?.reason === "disabled_by_server"
      ? "AI features are disabled on this server (AI_REWRITING_ENABLED=false). Nothing can be generated."
      : "The AI provider is not configured. Add an API key in backend/.env to generate a letter."
    : !aiPreference
    ? "AI features are turned off in your Settings. Turn them on to generate a cover letter."
    : null

  return (
    <div className="bg-surface rounded-2xl border border-edge overflow-hidden mb-6">
      <div className="px-6 py-4 border-b border-edge flex flex-wrap items-center gap-2">
        <FileText size={16} className="text-teal" />
        <h2 className="font-display font-semibold text-base text-navy">Cover Letter</h2>
        <span className="ml-auto text-xs text-dim">Uses your resume facts and this job only</span>
      </div>

      <div className="p-5 space-y-4">
        {loadingPreview ? (
          <div className="flex items-center gap-2 text-sm text-mid">
            <Loader2 size={15} className="animate-spin" />
            Loading what would be sent…
          </div>
        ) : previewError ? (
          <p className="text-sm text-red">{previewError}</p>
        ) : source ? (
          <>
            <div className="rounded-xl border border-edge bg-warm p-4">
              <div className="flex items-center gap-2 mb-2">
                <Shield size={14} className="text-teal" />
                <p className="text-sm font-medium text-navy">Exactly what leaves this machine</p>
              </div>
              <ul className="text-xs text-mid space-y-1">
                <li>Name and headline: <span className="text-navy">{source.candidate.name || "(not provided)"}{source.candidate.headline ? ` — ${source.candidate.headline}` : ""}</span></li>
                <li>Summary: {source.candidate.summary ? `${source.candidate.summary.length} characters` : "not included"}</li>
                <li>Experience: {source.limits.experience_bullets} bullet{source.limits.experience_bullets === 1 ? "" : "s"} from {source.experience.length} role{source.experience.length === 1 ? "" : "s"}</li>
                <li>Skills: {source.limits.skills}{source.skills.length > 0 ? ` — ${source.skills.slice(0, 6).join(", ")}${source.skills.length > 6 ? "…" : ""}` : ""}</li>
                <li>Job posting: {source.limits.job_description_chars} characters (title, company, required/preferred skills, excerpt)</li>
              </ul>
              <p className="text-[10px] text-dim mt-2">
                Email, phone, location, and links are never sent. The preview above is built locally — no AI call is made until you press Generate.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-navy">Tone</span>
              {TONES.map(option => (
                <button
                  key={option.value}
                  onClick={() => setTone(option.value)}
                  title={option.hint}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    tone === option.value
                      ? "bg-navy text-white border-navy"
                      : "bg-surface text-mid border-edge hover:border-navy/30"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            {unavailableMessage ? (
              <div className="flex items-start gap-2 rounded-xl border border-edge bg-off p-3">
                <AlertTriangle size={14} className="text-[#B45309] shrink-0 mt-0.5" />
                <p className="text-xs text-mid">{unavailableMessage}</p>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={generate}
                  disabled={generating}
                  className="flex items-center gap-2 px-5 py-2.5 bg-teal text-navy text-sm font-semibold rounded-xl hover:bg-teal-dim transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ boxShadow: "0 2px 12px rgba(0,201,167,0.25)" }}
                >
                  {generating ? <><Loader2 size={14} className="animate-spin" /> Writing…</> : <><Sparkles size={14} /> Generate cover letter</>}
                </button>
                {preview?.provider && (
                  <p className="text-[10px] text-dim">
                    Sends the facts above to {preview.provider}{preview.model ? ` (${preview.model})` : ""}. Nothing is saved.
                  </p>
                )}
              </div>
            )}

            {result && (
              <div className="space-y-3">
                {result.guard.status === "flagged" && (
                  <div className="flex items-start gap-2 rounded-xl border border-[rgba(245,158,11,0.3)] bg-[rgba(245,158,11,0.08)] p-3">
                    <AlertTriangle size={14} className="text-[#B45309] shrink-0 mt-0.5" />
                    <div className="text-xs text-mid">
                      <p className="font-medium text-navy">Review this draft before using it.</p>
                      <ul className="list-disc ml-4 mt-1 space-y-0.5">
                        {result.guard.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
                      </ul>
                      <p className="mt-1">The guard could not verify every claim against your resume facts{result.guard.retried ? " after one retry" : ""}.</p>
                    </div>
                  </div>
                )}

                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                    <label className="text-xs font-medium text-navy">Draft — edit before sending</label>
                    <span className="text-[10px] text-dim font-code">{text.split(/\s+/).filter(Boolean).length} words</span>
                  </div>
                  <textarea
                    value={text}
                    onChange={e => setText(e.target.value)}
                    rows={14}
                    className="w-full px-4 py-3 rounded-xl border border-edge bg-warm text-sm text-navy leading-relaxed outline-none focus:border-2 focus:border-navy transition-all resize-y font-body"
                  />
                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <button
                      onClick={copy}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-mid border border-edge rounded-lg hover:border-navy/30 hover:text-navy transition-all"
                    >
                      {copied ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
                    </button>
                    <button
                      onClick={download}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-mid border border-edge rounded-lg hover:border-navy/30 hover:text-navy transition-all"
                    >
                      <Download size={12} /> Download .txt
                    </button>
                    <p className="text-[10px] text-dim ml-auto">
                      {result.guard.status === "passed" ? "No unsupported numbers or skills detected." : "Flagged — not automatically safe."}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  )
}
