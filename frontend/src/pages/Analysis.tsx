import { useState } from "react"
import { Download, RefreshCw, ChevronDown, ChevronUp, Copy, CheckCircle, Check, XCircle, AlertTriangle, Lightbulb, BarChart2, Target, Edit3, Zap, BookOpen, ArrowLeftRight, Shield, Save, Info } from "lucide-react"
import type { PageProps } from "../types"
import * as api from "../api"

/* ─── Score Gauge ─────────────────────────────────────────── */
function ScoreGauge({ score, size = 160 }: { score: number; size?: number }) {
  const r = size * 0.4
  const circ = 2 * Math.PI * r
  const filled = circ * (score / 100)
  const cx = size / 2
  const cy = size / 2
  const color = score >= 75 ? "#00C9A7" : score >= 50 ? "#FFB800" : "#FF4757"
  const glow = score >= 75
    ? "drop-shadow(0 0 14px rgba(0,201,167,0.55))"
    : score >= 50
    ? "drop-shadow(0 0 14px rgba(255,184,0,0.55))"
    : "drop-shadow(0 0 14px rgba(255,71,87,0.55))"
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} style={{ width: size, height: size }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#E4E8F0" strokeWidth={size * 0.08} />
        <circle
          cx={cx} cy={cy} r={r}
          fill="none" stroke={color} strokeWidth={size * 0.08}
          strokeDasharray={`${filled} ${circ - filled}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ filter: glow }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span style={{ fontFamily: "DM Mono, monospace", fontSize: size * 0.23, color: "#1B2A4A", fontWeight: 500, lineHeight: 1 }}>{score}</span>
        <span style={{ fontFamily: "Inter, sans-serif", fontSize: size * 0.1, color: "#9AA5BE" }}>/ 100</span>
      </div>
    </div>
  )
}

/* ─── Mini bar ───────────────────────────────────────────── */
function MiniBar({ val, color }: { val: number; color: string }) {
  return (
    <div className="h-2 bg-off rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${val}%`, background: color }} />
    </div>
  )
}

/* ─── Keyword pill ─────────────────────────────────────────── */
function KwPill({ word, matched }: { word: string; matched: boolean }) {
  return (
    <span
      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border"
      style={matched
        ? { background: "rgba(0,201,167,0.1)", color: "#00A88A", borderColor: "rgba(0,201,167,0.3)" }
        : { background: "rgba(255,71,87,0.08)", color: "#E53E4B", borderColor: "rgba(255,71,87,0.25)" }
      }
    >
      {!matched && <span className="mr-1 opacity-60">+</span>}{word}
    </span>
  )
}

/* ─── Accordion card ─────────────────────────────────────── */
type AnalysisIssue = { title: string; severity: "critical" | "warning"; summary: string; detail: string; fix: string }
type AnalysisBullet = { text: string; section: string; verbType: "strong" | "weak" | "missing"; hasMetric: boolean; metric: string; suggestions: string[] }
type AnalysisRewrite = { original: string; moderate: string; aggressive: string; guard?: { status: string; reasons: string[]; retried: boolean; rejected_variants?: string[] } }

function IssueCard({ issue }: { issue: AnalysisIssue }) {
  const [open, setOpen] = useState(false)
  const isCrit = issue.severity === "critical"
  return (
    <div
      className="rounded-xl border overflow-hidden transition-all"
      style={{ borderColor: isCrit ? "rgba(255,71,87,0.2)" : "rgba(255,184,0,0.2)", background: isCrit ? "rgba(255,71,87,0.03)" : "rgba(255,184,0,0.03)" }}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3.5 text-left"
      >
        {isCrit
          ? <XCircle size={16} className="text-red shrink-0" />
          : <AlertTriangle size={16} className="text-amber shrink-0" />
        }
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-navy">{issue.title}</span>
            <span
              className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase"
              style={isCrit
                ? { background: "rgba(255,71,87,0.12)", color: "#FF4757" }
                : { background: "rgba(255,184,0,0.12)", color: "#D97706" }
              }
            >{issue.severity}</span>
          </div>
          <p className="text-xs text-mid mt-0.5">{issue.summary}</p>
        </div>
        {open ? <ChevronUp size={15} className="text-dim shrink-0" /> : <ChevronDown size={15} className="text-dim shrink-0" />}
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-edge">
          <p className="text-sm text-mid leading-relaxed mt-3 mb-3">{issue.detail}</p>
          <div className="flex items-start gap-2 p-3 rounded-lg bg-surface">
            <Lightbulb size={14} className="text-teal mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-navy mb-0.5">How to Fix</p>
              <p className="text-xs text-mid leading-relaxed">{issue.fix}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ─── Bullet card ────────────────────────────────────────── */
function BulletCard({ bullet }: { bullet: AnalysisBullet }) {
  const [copied, setCopied] = useState(false)
  const badgeStyles = {
    strong:  { bg: "rgba(0,201,167,0.1)",   color: "#00A88A",  label: "Strong Verb" },
    weak:    { bg: "rgba(255,184,0,0.1)",    color: "#D97706",  label: "Weak Verb" },
    missing: { bg: "rgba(255,71,87,0.1)",    color: "#E53E4B",  label: "No Action Verb" },
  }
  const s = badgeStyles[bullet.verbType]
  const copy = (text: string) => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }
  return (
    <div className="bg-surface rounded-xl border border-edge p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1">
          <p className="text-sm text-navy leading-relaxed">{bullet.text}</p>
          <span className="text-[10px] text-dim uppercase tracking-wide">{bullet.section}</span>
        </div>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase shrink-0" style={s}>{s.label}</span>
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-mid">Metrics:</span>
          {bullet.hasMetric
            ? <span className="text-xs font-medium text-teal flex items-center gap-0.5"><CheckCircle size={11} /> Yes — <span className="font-code">{bullet.metric}</span></span>
            : <span className="text-xs font-medium text-red flex items-center gap-0.5"><XCircle size={11} /> No quantifiable data</span>
          }
        </div>
        {bullet.verbType === "weak" && bullet.suggestions && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-mid">Replace with:</span>
            {bullet.suggestions.map(s => (
              <button
                key={s}
                onClick={() => copy(s)}
                className="text-xs px-2 py-0.5 rounded-md font-medium text-teal hover:bg-teal/10 transition-colors border border-teal/20"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── AI Rewrite card ────────────────────────────────────── */
function RewriteCard({ item }: { item: AnalysisRewrite }) {
  const [copied, setCopied] = useState<string | null>(null)
  const copy = (text: string, key: string) => { navigator.clipboard.writeText(text); setCopied(key); setTimeout(() => setCopied(null), 1800) }
  const rejectedVariants = item.guard?.rejected_variants
  const guardRejected = item.guard?.status === "rejected" || rejectedVariants?.length === 2
  const partiallyRejected = item.guard?.status === "partially_rejected"
  const retryFailed = item.guard?.status === "retry_failed"
  const note = "AI suggestion not shown: it added details that aren't in your original bullet."
  const retryNote = "Some AI suggestions are hidden: the first draft added details that aren't in your original bullet, and the second attempt didn't complete. Re-analyze to try again."
  return (
    <div className="bg-surface rounded-2xl border border-edge overflow-hidden">
      <div className="px-5 py-3.5 border-b border-edge bg-off">
        <p className="text-xs font-semibold text-mid uppercase tracking-wide">Original</p>
        <p className="text-sm text-mid leading-relaxed mt-1 italic">"{item.original}"</p>
      </div>
      <div className="p-5 space-y-4">
        {guardRejected
          ? <p className="text-sm text-dim italic">{note}</p>
          : [
          { key: "moderate", label: "Moderate Rewrite", sublabel: "Clearer, stronger", text: item.moderate, color: "#00C9A7" },
          { key: "aggressive", label: "Aggressive Rewrite", sublabel: "Maximum impact", text: item.aggressive, color: "#8B5CF6" },
          ].filter(v => rejectedVariants
            ? !rejectedVariants.includes(v.key)
            : (!partiallyRejected || v.text !== item.original)
          ).map(v => (
          <div key={v.key}>
            <div className="flex items-center justify-between mb-1.5">
              <div>
                <span className="text-xs font-bold" style={{ color: v.color }}>{v.label}</span>
                <span className="text-xs text-dim ml-2">{v.sublabel}</span>
              </div>
              <button
                onClick={() => copy(v.text, v.key)}
                className="flex items-center gap-1 text-[11px] text-mid hover:text-navy transition-colors px-2 py-1 rounded-md hover:bg-off"
              >
                {copied === v.key ? <><CheckCircle size={11} className="text-teal" /> Copied!</> : <><Copy size={11} /> Copy</>}
              </button>
            </div>
            <p className="text-sm text-navy leading-relaxed bg-warm rounded-lg px-3 py-2.5 border border-edge">{v.text}</p>
          </div>
        ))}
        {(partiallyRejected || (retryFailed && rejectedVariants?.length !== 2)) && <p className="text-sm text-dim italic">{retryFailed ? retryNote : note}</p>}
        {retryFailed && rejectedVariants?.length === 2 && <p className="text-sm text-dim italic">{retryNote}</p>}
      </div>
    </div>
  )
}

/* ─── Page ───────────────────────────────────────────────── */
export default function Analysis({ navigate, addToast }: PageProps) {
  const [passedOpen, setPassedOpen] = useState(false)
  const [exportLoading, setExportLoading] = useState(false)
  // A4: the export keeps the resume's own title by default; matching the
  // job posting's title is an explicit, per-export choice.
  const [matchTitle, setMatchTitle] = useState(false)
  const [saveVersionLoading, setSaveVersionLoading] = useState(false)
  // A3: which missing keywords the user ticked as "skills I actually have"
  const [selectedKws, setSelectedKws] = useState<string[]>([])
  const [confirmLoading, setConfirmLoading] = useState(false)
  const [newlyConfirmed, setNewlyConfirmed] = useState<string[]>([])
  const analysis = api.getLastAnalysis()
  const resumeMeta = api.getLastResumeMeta()

  const handleExport = async () => {
    const resumeId = api.getLastResumeId()
    if (!resumeId) { addToast("error", "No resume selected for export"); return }
    setExportLoading(true)
    addToast("info", "Generating ATS-optimized DOCX…")
    try {
      // A18: pin the export to the analysis being viewed on this page.
      const blob = await api.exportResume(resumeId, analysis?.id, matchTitle)
      const link = document.createElement("a")
      link.href = URL.createObjectURL(blob)
      link.download = "ATS_Optimized_Resume.docx"
      link.click()
      URL.revokeObjectURL(link.href)
      addToast("success", "ATS-optimized resume downloaded!")
    } catch (error) { addToast("error", error instanceof Error ? error.message : "Could not export resume") }
    finally { setExportLoading(false) }
  }

  // D3: store the tailored text as a per-job version (rewrites applied for real).
  const handleSaveVersion = async () => {
    const resumeId = api.getLastResumeId()
    if (!resumeId || !analysis?.id) { addToast("error", "No resume selected"); return }
    setSaveVersionLoading(true)
    try {
      await api.createVersion(resumeId, analysis.id)
      addToast("success", "Tailored version saved! Export it anytime from the Dashboard.")
    } catch (error) { addToast("error", error instanceof Error ? error.message : "Could not save version") }
    finally { setSaveVersionLoading(false) }
  }

  // A3: confirm the ticked missing keywords so they reach the exported
  // resume's Skills section. Honesty rule: only confirm skills you have.
  const toggleKw = (k: string) => {
    setSelectedKws(prev => prev.includes(k) ? prev.filter(x => x !== k) : [...prev, k])
  }

  const handleConfirmKeywords = async () => {
    const resumeId = api.getLastResumeId()
    if (!resumeId || !analysis?.id || selectedKws.length === 0) return
    setConfirmLoading(true)
    try {
      const res = await api.confirmKeywords(resumeId, analysis.id, selectedKws)
      setNewlyConfirmed(res.confirmed_keywords)
      setSelectedKws([])
      if (analysis.report) {
        api.saveLastAnalysis({
          ...analysis,
          report: { ...analysis.report, confirmed_keywords: res.confirmed_keywords },
        })
      }
      if (res.soft_skipped && res.soft_skipped.length > 0) {
        addToast("info", `${res.soft_skipped.join(", ")} ${res.soft_skipped.length === 1 ? "is a soft skill" : "are soft skills"} — show ${res.soft_skipped.length === 1 ? "it" : "them"} in your bullets instead, not in Skills.`)
      }
      addToast("success", `${res.confirmed_keywords.length} technical skill${res.confirmed_keywords.length === 1 ? "" : "s"} will be added to your exported resume.`)
    } catch (error) { addToast("error", error instanceof Error ? error.message : "Could not confirm keywords") }
    finally { setConfirmLoading(false) }
  }

  const report = analysis?.report
  // F5: without an analysis there is nothing to show -- never render a zeroed-out report.
  if (!analysis) {
    return (
      <div className="min-h-screen bg-warm">
        <div className="max-w-5xl mx-auto px-6 py-20 text-center">
          <h1 className="font-display font-bold text-2xl text-navy mb-2">No analysis to show</h1>
          <p className="text-sm text-mid mb-6">Run an analysis from the Upload page and the full report will appear here.</p>
          <button
            onClick={() => navigate("upload")}
            className="px-5 py-2.5 bg-navy text-white text-sm font-semibold rounded-xl hover:bg-navy-light transition-all"
          >
            Go to Upload
          </button>
        </div>
      </div>
    )
  }
  const atsIssues: AnalysisIssue[] = (report?.ats?.issues ?? []).map(issue => ({
    title: issue.issue,
    severity: issue.category,
    summary: issue.issue,
    detail: issue.fix,
    fix: issue.fix,
  }))
  const passedChecks = report?.ats?.passed ?? []
  const matchedKws = report?.keyword_analysis?.matched_keywords ?? []
  const missingKws = report?.keyword_analysis?.missing_keywords ?? []
  // A3: soft skills (Communication, Leadership, ...) are advice only — they
  // are never added to the Skills section; they belong in bullets.
  const softMissing = report?.keyword_analysis?.soft_missing_keywords ?? []
  // A3: keywords the user confirmed they actually have (stored on the
  // analysis + anything confirmed during this visit)
  const confirmedKws = Array.from(new Set([
    ...((report?.confirmed_keywords ?? []) as string[]),
    ...newlyConfirmed,
  ]))
  const bullets: AnalysisBullet[] = (report?.bullet_analysis?.details ?? []).map(bullet => ({
    text: bullet.original,
    section: bullet.section ?? "Experience",
    verbType: bullet.verb_type,
    hasMetric: bullet.has_metrics,
    metric: bullet.metrics.join(", "),
    suggestions: bullet.suggestion.replace(/^Replace with:\s*/i, "").split(", ").filter(Boolean),
  }))
  const rewrites: AnalysisRewrite[] = Object.entries(report?.ai_rewritten_examples ?? {}).filter(([, rewrite]) => typeof rewrite === "object" && (rewrite.source === "openai" || rewrite.source === "groq" || rewrite.source === "guard_rejected")).map(([original, rewrite]) => {
    const value = typeof rewrite === "string" ? { moderate: rewrite, aggressive: rewrite } : rewrite
    return { original, moderate: value.moderate ?? value.ai_output ?? original, aggressive: value.aggressive ?? value.moderate ?? value.ai_output ?? original, guard: value.guard }
  })
  const aiErrorEntries = Object.values(report?.ai_rewritten_examples ?? {}).filter(
    rewrite => typeof rewrite === "object" && rewrite.guard?.status === "ai_error"
  )
  const aiErrorCause = aiErrorEntries
    .map(rewrite => (typeof rewrite === "object" ? rewrite.error : undefined))
    .find(Boolean)
  const hasAiErrors = aiErrorEntries.length > 0
  const grammarIssues = (report?.grammar?.typos_found ?? []).map(typo => ({ wrong: typo.word, right: typo.suggestion, context: `Found in the uploaded resume`, line: null }))
  // Older saved analyses have no flags -> treated as available. New ones set score_available=false
  // when there is no job description (keywords) or no bullets were parsed (bullet impact).
  const kwAvailable = report?.keyword_analysis?.score_available !== false
  const bulletAvailable = report?.bullet_analysis?.score_available !== false
  const excludedNote = [
    !kwAvailable && `Keyword Match (${report?.keyword_analysis?.reason ?? "unavailable"})`,
    !bulletAvailable && `Bullet Impact (${report?.bullet_analysis?.warning ?? "unavailable"})`,
  ].filter(Boolean) as string[]
  const overall = analysis.overall_score
  const verdict = overall >= 75 ? "ATS-Ready!" : overall >= 50 ? "Almost there!" : "Needs significant work"
  const verdictColor = overall >= 75 ? "#00C9A7" : overall >= 50 ? "#D97706" : "#FF4757"
  // D1: projected after-tailoring scores (absent when no rewrite changed a bullet)
  const improvement = report?.improvement
  const deltaPct = (v: number | null | undefined) => (v == null ? null : Math.round(v))

  return (
    <div className="min-h-screen bg-warm pb-28">
      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* Header */}
        <div className="flex items-start justify-between mb-8 flex-wrap gap-4">
          <div>
            <p className="text-xs text-mid font-medium uppercase tracking-wider mb-1">Analysis Report</p>
            <h1 className="font-display font-bold text-2xl text-navy">{resumeMeta?.filename ?? "Resume analysis"}</h1>
            <p className="text-sm text-mid mt-0.5">Analyzed against: <span className="font-medium text-navy">{resumeMeta?.jobTitle ?? "Selected job description"}</span>{analysis?.created_at && ` · ${new Date(analysis.created_at).toLocaleDateString()}`}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { addToast("info", "Re-analysis queued…"); navigate("upload") }}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-navy border border-edge rounded-xl hover:bg-off transition-all"
            >
              <RefreshCw size={14} />
              Re-Analyze
            </button>
            <button
              onClick={() => navigate("jobs")}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-navy border border-edge rounded-xl hover:bg-off transition-all"
            >
              <ArrowLeftRight size={14} />
              Different Job
            </button>
          </div>
        </div>

        {/* Overall score hero */}
        <div className="bg-surface rounded-2xl border border-edge p-8 mb-6 flex flex-col md:flex-row items-center gap-8">
          <div className="flex flex-col items-center">
            <ScoreGauge score={overall} size={160} />
            <div className="mt-4 text-center">
              <p className="font-display font-bold text-xl" style={{ color: verdictColor }}>{verdict}</p>
              <p className="text-sm text-mid mt-1">{atsIssues.filter(issue => issue.severity === "critical").length} critical issues · {atsIssues.filter(issue => issue.severity === "warning").length} warnings</p>
            </div>
          </div>
          <div className="flex-1 space-y-5">
            <div>
              <p className="text-xs font-semibold text-mid uppercase tracking-wider mb-3">Score Breakdown</p>
              <div className="space-y-3">
                {([
                  { label: "ATS Compatibility", val: analysis?.ats_score ?? null, color: "#FFB800" },
                  { label: "Keyword Match",     val: kwAvailable ? (analysis?.keyword_score ?? null) : null, color: "#FF4757" },
                  { label: "Bullet Impact",     val: bulletAvailable ? (analysis?.bullet_score ?? null) : null, color: "#00C9A7" },
                ] as { label: string; val: number | null; color: string }[]).map(s => (
                  <div key={s.label}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-medium text-navy">{s.label}</span>
                      <span className="font-code text-sm font-medium" style={{ color: s.val === null ? "#8A94A6" : s.color }}>{s.val === null ? "N/A" : `${s.val}%`}</span>
                    </div>
                    <MiniBar val={s.val ?? 0} color={s.color} />
                  </div>
                ))}
              </div>
            </div>
            {excludedNote.length > 0 && (
              <p className="text-xs text-mid bg-off rounded-lg px-3 py-2">
                Not included in the overall score: {excludedNote.join("; ")}. The remaining scores were re-weighted.
              </p>
            )}
            <div className="flex items-center gap-3 pt-2">
              <div className="flex items-center gap-1.5 text-xs text-mid">
                <div className="w-2 h-2 rounded-full bg-red" /><span>Critical issue</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-mid">
                <div className="w-2 h-2 rounded-full bg-amber" /><span>Warning</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-mid">
                <div className="w-2 h-2 rounded-full bg-teal" /><span>Passed</span>
              </div>
            </div>
          </div>
        </div>

        {/* D1: projected improvement from the applied AI rewrites */}
        {improvement && (() => {
          const before = improvement.before
          const after = improvement.after
          const delta = Math.round(after.overall - before.overall)
          const rows = [
            { label: "Bullet Impact", from: deltaPct(before.bullets), to: deltaPct(after.bullets) },
            { label: "Keyword Match", from: deltaPct(before.keywords), to: deltaPct(after.keywords) },
          ] as { label: string; from: number | null; to: number | null }[]
          return (
            <div className="bg-surface rounded-2xl border border-edge p-6 mb-6">
              <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <p className="text-xs font-semibold text-mid uppercase tracking-wider">Projected After Tailoring</p>
                <span className="text-[11px] text-mid bg-off rounded-full px-2.5 py-1">
                  {improvement.applied_rewrites} of {improvement.flagged_bullets} flagged bullets rewritten
                </span>
              </div>
              <div className="flex items-center gap-4 mb-4 flex-wrap">
                <span className="font-code text-2xl text-mid line-through decoration-edge">{Math.round(before.overall)}</span>
                <span className="text-mid">→</span>
                <span className="font-code text-4xl font-medium text-teal">{Math.round(after.overall)}</span>
                {delta !== 0 && (
                  <span className={`font-code text-sm font-semibold rounded-full px-2.5 py-1 ${delta > 0 ? "text-teal bg-teal/10" : "text-red bg-red/10"}`}>
                    {delta > 0 ? "+" : ""}{delta} pts
                  </span>
                )}
              </div>
              <div className="space-y-2">
                {rows.map(row => (
                  <div key={row.label} className="flex items-center justify-between text-sm">
                    <span className="text-mid">{row.label}</span>
                    {row.to != null ? (
                      <span className="font-code text-navy">
                        {row.from ?? "N/A"} → <span className="font-semibold text-teal">{row.to}</span>
                      </span>
                    ) : (
                      <span className="font-code text-mid">N/A</span>
                    )}
                  </div>
                ))}
              </div>
              <p className="text-xs text-mid bg-off rounded-lg px-3 py-2 mt-4">
                Scores re-computed with the AI-rewritten bullets in place. ATS compatibility stays the same — it measures formatting, not wording.
              </p>
              {analysis.job_id && (
                <button
                  onClick={handleSaveVersion}
                  disabled={saveVersionLoading}
                  className="mt-3 flex items-center gap-2 px-4 py-2 bg-navy text-white text-xs font-semibold rounded-xl hover:bg-navy-light transition-all disabled:opacity-50"
                >
                  <Save size={13} />
                  {saveVersionLoading ? "Saving version…" : "Save as version for this job"}
                </button>
              )}
            </div>
          )
        })()}

        {/* 3 breakdown cards */}
        <div className="grid md:grid-cols-3 gap-4 mb-6">
          {/* ATS Compat */}
          <div className="bg-surface rounded-2xl border border-edge p-5">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-amber/10 flex items-center justify-center">
                <Shield size={16} className="text-amber" />
              </div>
              <p className="font-display font-semibold text-sm text-navy">ATS Compatibility</p>
            </div>
            <p className="font-code text-3xl font-medium text-amber mb-4">{analysis.ats_score ?? "N/A"}{analysis.ats_score != null && <span className="text-lg text-mid">/100</span>}</p>
            <div className="space-y-1.5">
              {atsIssues.map((issue, i) => (
                <div key={i} className="flex items-start gap-1.5">
                  {issue.severity === "critical"
                    ? <XCircle size={13} className="text-red shrink-0 mt-0.5" />
                    : <AlertTriangle size={13} className="text-amber shrink-0 mt-0.5" />
                  }
                  <p className="text-xs text-mid leading-tight">{issue.title}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Keyword Match */}
          <div className="bg-surface rounded-2xl border border-edge p-5">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-red/10 flex items-center justify-center">
                <Target size={16} className="text-red" />
              </div>
              <p className="font-display font-semibold text-sm text-navy">Keyword Match</p>
            </div>
            <p className="font-code text-3xl font-medium text-red mb-1">{kwAvailable ? (analysis.keyword_score ?? "N/A") : "N/A"}{kwAvailable && analysis.keyword_score != null && <span className="text-lg text-mid">%</span>}</p>
            <p className="text-xs text-dim mb-3">{kwAvailable ? `Cosine similarity: ${report?.keyword_analysis?.similarity ?? 0}%` : (report?.keyword_analysis?.reason ?? "Select a job description to score keywords.")}</p>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-xs text-mid w-14 shrink-0">Matched</span>
                <div className="flex-1 h-1.5 bg-off rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-teal" style={{ width: `${matchedKws.length ? matchedKws.length / (matchedKws.length + missingKws.length) * 100 : 0}%` }} />
                </div>
                <span className="text-xs font-code text-teal">{matchedKws.length}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-mid w-14 shrink-0">Missing</span>
                <div className="flex-1 h-1.5 bg-off rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-red" style={{ width: `${missingKws.length ? missingKws.length / (matchedKws.length + missingKws.length) * 100 : 0}%` }} />
                </div>
                <span className="text-xs font-code text-red">{missingKws.length}</span>
              </div>
            </div>
          </div>

          {/* Bullet Impact */}
          <div className="bg-surface rounded-2xl border border-edge p-5">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-teal/10 flex items-center justify-center">
                <BarChart2 size={16} className="text-teal" />
              </div>
              <p className="font-display font-semibold text-sm text-navy">Bullet Impact</p>
            </div>
            <p className="font-code text-3xl font-medium text-teal mb-4">{bulletAvailable ? (analysis.bullet_score ?? "N/A") : "N/A"}{bulletAvailable && analysis.bullet_score != null && <span className="text-lg text-mid">/100</span>}</p>
            {!bulletAvailable && <p className="text-xs text-dim mb-3">{report?.bullet_analysis?.warning}</p>}
            <div className="grid grid-cols-2 gap-2">
                {[
                { label: "Total bullets", val: String(report?.bullet_analysis?.total_bullets ?? 0), color: "#1B2A4A" },
                { label: "With metrics",  val: String(report?.bullet_analysis?.bullets_with_metrics ?? 0), color: "#00C9A7" },
                { label: "Strong verbs",  val: String(report?.bullet_analysis?.strong_verbs_count ?? 0), color: "#00C9A7" },
                { label: "Weak verbs",    val: String(report?.bullet_analysis?.weak_verbs_count ?? 0), color: "#D97706" },
              ].map(s => (
                <div key={s.label} className="bg-off rounded-lg px-2.5 py-2">
                  <p className="font-code font-medium text-sm" style={{ color: s.color }}>{s.val}</p>
                  <p className="text-[10px] text-dim">{s.label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ATS Issues */}
        <div className="bg-surface rounded-2xl border border-edge overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-edge flex items-center gap-2">
            <XCircle size={16} className="text-red" />
            <h2 className="font-display font-semibold text-base text-navy">ATS Issues</h2>
            <span className="ml-auto text-xs bg-red/10 text-red px-2 py-0.5 rounded-full font-medium">{atsIssues.length} issues</span>
          </div>
          <div className="p-5 space-y-3">
            {atsIssues.map((issue, i) => <IssueCard key={i} issue={issue} />)}

            {/* Passed checks */}
            <button
              onClick={() => setPassedOpen(!passedOpen)}
              className="w-full flex items-center gap-2 px-4 py-3 rounded-xl bg-teal/5 border border-teal/20 hover:bg-teal/8 transition-colors"
            >
              <CheckCircle size={15} className="text-teal" />
              <span className="text-sm font-medium text-teal flex-1 text-left">Passed Checks ({passedChecks.length})</span>
              {passedOpen ? <ChevronUp size={15} className="text-teal" /> : <ChevronDown size={15} className="text-teal" />}
            </button>
            {passedOpen && (
              <div className="rounded-xl bg-teal/3 border border-teal/15 px-4 py-3 space-y-2">
                {passedChecks.map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <CheckCircle size={12} className="text-teal shrink-0" />
                    <p className="text-xs text-mid">{c}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Keyword Gap */}
        <div className="bg-surface rounded-2xl border border-edge overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-edge flex items-center gap-2">
            <Target size={16} className="text-mid" />
            <h2 className="font-display font-semibold text-base text-navy">Keyword Gap Analysis</h2>
          </div>
          <div className="p-5">
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <p className="text-xs font-semibold text-teal uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <CheckCircle size={12} /> Matched ({matchedKws.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {matchedKws.map(k => <KwPill key={k} word={k} matched />)}
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold text-red uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <XCircle size={12} /> Missing ({missingKws.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {missingKws.map(k => {
                    if (softMissing.includes(k)) {
                      return (
                        <span
                          key={k}
                          title="Soft skill — show it in a bullet where you actually used it; it isn't added to the Skills section."
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border border-dashed"
                          style={{ background: "rgba(217,119,6,0.06)", color: "#B45309", borderColor: "rgba(217,119,6,0.35)" }}
                        >
                          <Info size={11} /> {k}
                        </span>
                      )
                    }
                    const isConfirmed = confirmedKws.includes(k)
                    const isSelected = selectedKws.includes(k)
                    if (isConfirmed) {
                      return (
                        <span
                          key={k}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border"
                          style={{ background: "rgba(0,201,167,0.1)", color: "#00A88A", borderColor: "rgba(0,201,167,0.3)" }}
                        >
                          <CheckCircle size={11} /> {k}
                        </span>
                      )
                    }
                    return (
                      <button
                        key={k}
                        onClick={() => toggleKw(k)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-all cursor-pointer hover:opacity-80"
                        style={isSelected
                          ? { background: "#1B2A4A", color: "#FFFFFF", borderColor: "#1B2A4A" }
                          : { background: "rgba(255,71,87,0.08)", color: "#E53E4B", borderColor: "rgba(255,71,87,0.25)" }
                        }
                      >
                        {isSelected ? <Check size={11} /> : <span className="opacity-60">+</span>}{k}
                      </button>
                    )
                  })}
                </div>
                {missingKws.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs text-dim leading-relaxed mb-2">
                      Tick only the technical skills you actually have — confirmed keywords are added to the matching line of your exported resume's Skills section (e.g. "Databases: MySQL, SQL"). Never confirm a skill you couldn't discuss in an interview.
                    </p>
                    {softMissing.length > 0 && (
                      <p className="text-xs leading-relaxed mb-2" style={{ color: "#B45309" }}>
                        <Info size={11} className="inline mr-1 -mt-0.5" />
                        Soft skills ({softMissing.join(", ")}) aren't added to the Skills section — show them in your bullets where you actually used them.
                      </p>
                    )}
                    {selectedKws.length > 0 && (
                      <button
                        onClick={handleConfirmKeywords}
                        disabled={confirmLoading}
                        className="px-4 py-2 bg-navy text-white text-xs font-semibold rounded-xl hover:bg-navy-light transition-all disabled:opacity-50"
                      >
                        {confirmLoading ? "Confirming…" : `Add ${selectedKws.length} skill${selectedKws.length === 1 ? "" : "s"} to my resume`}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
            <div className="mt-5 p-3 bg-amber/5 border border-amber/20 rounded-xl flex items-start gap-2">
              <Lightbulb size={14} className="text-amber shrink-0 mt-0.5" />
              <p className="text-xs text-mid leading-relaxed">
                <span className="font-semibold text-navy">Tip:</span> Add missing keywords like {missingKws.slice(0, 3).map((keyword, index) => <span key={keyword}>{index > 0 ? ", " : ""}"{keyword}"</span>)} naturally into your Experience bullets and Skills section. Avoid keyword stuffing — integrate them into meaningful context.
              </p>
            </div>
          </div>
        </div>

        {/* Bullet Analysis */}
        <div className="bg-surface rounded-2xl border border-edge overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-edge flex items-center gap-2">
            <Edit3 size={16} className="text-mid" />
            <h2 className="font-display font-semibold text-base text-navy">Bullet-by-Bullet Analysis</h2>
                <span className="ml-auto text-xs text-dim font-code">{bullets.length} shown</span>
          </div>
          <div className="p-5 space-y-3">
            {bullets.map((b, i) => <BulletCard key={i} bullet={b} />)}
          </div>
        </div>

        {/* AI Rewrites */}
        <div className="bg-surface rounded-2xl border border-edge overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-edge flex items-center gap-2">
            <Zap size={16} className="text-teal" />
            <h2 className="font-display font-semibold text-base text-navy">AI Rewrite Suggestions</h2>
                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-teal/10 text-teal ml-1">Backend AI</span>
          </div>
          <div className="p-5 space-y-4">
            <p className="text-sm text-mid">Weakest bullets, rewritten in two intensities. Review each one before pasting it into your resume.</p>
            {hasAiErrors && <p className="text-xs text-dim">AI suggestions couldn't be generated for some bullets{aiErrorCause ? `: ${aiErrorCause}.` : " (the AI service didn't respond)."} Re-analyze to try again.</p>}
            {rewrites.length > 0
              ? rewrites.map((r, i) => <RewriteCard key={i} item={r} />)
              : <div className="rounded-xl border border-amber/20 bg-amber/5 p-4 text-sm text-mid">AI rewrites are unavailable for this analysis. Check the backend AI configuration and run the analysis again; rule-based suggestions remain available in the bullet cards above.</div>}
          </div>
        </div>

        {/* Grammar */}
        <div className="bg-surface rounded-2xl border border-edge overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-edge flex items-center gap-2">
            <BookOpen size={16} className="text-mid" />
            <h2 className="font-display font-semibold text-base text-navy">Grammar & Spelling</h2>
            <span className="ml-auto text-xs bg-amber/10 text-amber px-2 py-0.5 rounded-full font-medium">{grammarIssues.length} issues</span>
          </div>
          <div className="p-5">
            <div className="space-y-3">
              {grammarIssues.map((g, i) => (
                <div key={i} className="flex items-center gap-4 p-3.5 rounded-xl bg-off border border-edge">
                  <div className="shrink-0">
                    <span className="line-through text-red text-sm font-medium">{g.wrong}</span>
                    <span className="text-mid mx-2 text-sm">→</span>
                    <span className="text-teal text-sm font-medium">{g.right}</span>
                  </div>
                  <div className="text-xs text-dim italic flex-1 hidden sm:block">…{g.context}…</div>
                  {g.line && <span className="text-[10px] font-code text-dim shrink-0">Line {g.line}</span>}
                </div>
              ))}
            </div>
            <p className="text-xs text-dim mt-4">Grammar check is tech-term aware — words like "microservices", "Kubernetes", and API names are not flagged as errors.</p>
          </div>
        </div>
      </div>

      {/* Sticky export bar */}
      <div
        className="fixed bottom-0 left-0 right-0 z-30 border-t border-edge"
        style={{ background: "rgba(255,255,255,0.9)", backdropFilter: "blur(16px)" }}
      >
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="font-display font-semibold text-navy text-sm">Ready to apply?</p>
            <p className="text-xs text-mid">Download your ATS-optimized resume with all formatting fixes applied.</p>
            {resumeMeta?.jobTitle && (
              <label className="mt-2 flex items-start gap-2 text-xs text-mid cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={matchTitle}
                  onChange={e => setMatchTitle(e.target.checked)}
                  className="mt-0.5"
                  style={{ accentColor: "#1B2A4A" }}
                />
                <span>
                  Match my title to this job (“{resumeMeta.jobTitle}”)
                  <span className="block text-dim">
                    Off by default — the export keeps your own title unless you tick this.
                  </span>
                </span>
              </label>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("jobs")}
              className="px-4 py-2.5 text-sm text-navy font-medium border border-edge rounded-xl hover:bg-off transition-all"
            >
              Analyze vs. Different Job
            </button>
            <button
              onClick={handleExport}
              disabled={exportLoading}
              className="flex items-center gap-2 px-5 py-2.5 bg-teal text-navy font-bold text-sm rounded-xl hover:bg-teal-dim transition-all disabled:opacity-70"
              style={{ boxShadow: "0 2px 12px rgba(0,201,167,0.3)" }}
            >
              {exportLoading
                ? <div className="w-4 h-4 border-2 border-navy/30 border-t-navy rounded-full animate-spin" />
                : <Download size={15} />
              }
              Download ATS-Optimized DOCX
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

