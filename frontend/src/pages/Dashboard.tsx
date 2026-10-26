import { useEffect, useState } from "react"
import { FileText, Briefcase, BarChart2, CheckSquare, Upload, Plus, ExternalLink, RefreshCw, Download, Lightbulb, ChevronRight, TrendingUp } from "lucide-react"
import type { PageProps } from "../types"
import * as api from "../api"

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) {
    return <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-code font-medium text-mid bg-off">N/A</span>
  }
  const color = score >= 75 ? "#00C9A7" : score >= 50 ? "#FFB800" : "#FF4757"
  const bg = score >= 75 ? "rgba(0,201,167,0.1)" : score >= 50 ? "rgba(255,184,0,0.1)" : "rgba(255,71,87,0.1)"
  return (
    <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-code font-medium" style={{ color, background: bg }}>
      {score}
    </span>
  )
}

function MiniGauge({ score, size = 44 }: { score: number; size?: number }) {
  const r = size * 0.38
  const circ = 2 * Math.PI * r
  const filled = circ * (score / 100)
  const color = score >= 75 ? "#00C9A7" : score >= 50 ? "#FFB800" : "#FF4757"
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} style={{ width: size, height: size }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E4E8F0" strokeWidth={size * 0.1} />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth={size * 0.1}
          strokeDasharray={`${filled} ${circ - filled}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span style={{ fontFamily: "DM Mono, monospace", fontSize: size * 0.22, color, fontWeight: 500 }}>{score}</span>
      </div>
    </div>
  )
}

const statCardMeta = [
  { icon: FileText,    label: "Resumes Uploaded",      iconBg: "rgba(59,130,246,0.1)", iconColor: "#3B82F6" },
  { icon: Briefcase,   label: "Job Descriptions Saved", iconBg: "rgba(139,92,246,0.1)", iconColor: "#8B5CF6" },
  { icon: BarChart2,   label: "Average ATS Score",      iconBg: "rgba(255,184,0,0.1)",  iconColor: "#FFB800", isScore: true },
  { icon: CheckSquare, label: "Analyses Completed",     iconBg: "rgba(0,201,167,0.1)",  iconColor: "#00C9A7" },
]

type RecentFile = {
  id: string
  name: string
  type: string
  date: string
  atsScore: number | null
  kwScore: number | null
  job: string
  analysis: api.ResumeSummary["latest_analysis"]
}

const tips = [
  "Avoid tables in your resume — most ATS parsers can't read them correctly.",
  "Use the exact job title from the posting in your summary section.",
  "Spell out acronyms at least once — write \"Application Programming Interface (API)\" the first time.",
  "Keep your resume to a single column layout for maximum ATS compatibility.",
  "Use standard section headers: Experience, Education, Skills — not creative names.",
]

function FileTypeBadge({ type }: { type: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    PDF:  { bg: "rgba(239,68,68,0.1)",   color: "#EF4444" },
    DOCX: { bg: "rgba(59,130,246,0.1)",  color: "#3B82F6" },
    TXT:  { bg: "rgba(107,114,128,0.1)", color: "#6B7280" },
  }
  const s = styles[type] ?? styles.TXT
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-code font-semibold uppercase" style={s}>{type}</span>
  )
}

export default function Dashboard({ navigate, addToast }: PageProps) {
  const [tipIdx, setTipIdx] = useState(0)
  const [recentFiles, setRecentFiles] = useState<RecentFile[]>([])
  const [firstName, setFirstName] = useState("")
  const [jobCount, setJobCount] = useState<number | null>(null)

  useEffect(() => {
    api.getMe().then(user => setFirstName(user.full_name.split(/\s+/)[0] ?? "")).catch(() => {})
    api.listJobs().then(jobs => setJobCount(jobs.length)).catch(() => setJobCount(null))
    api.listResumes().then(resumes => setRecentFiles(resumes.map(resume => ({
      id: resume.id,
      name: resume.filename,
      type: resume.file_type.replace(".", "").toUpperCase(),
      date: new Date(resume.created_at).toLocaleDateString(),
      atsScore: resume.latest_analysis?.ats_score ?? null,
      kwScore: resume.latest_analysis
        ? (resume.latest_analysis.report?.keyword_analysis?.score_available === false
          ? null
          : (resume.latest_analysis.keyword_score ?? null))
        : null,
      job: resume.latest_analysis?.job_id ? "Saved job description" : "General analysis",
      analysis: resume.latest_analysis,
    })))).catch(error => addToast("error", error.message))
  }, [addToast])

  // F13: real stats computed from the API; N/A when there is nothing to average.
  const analyzed = recentFiles.filter(f => f.analysis)
  const analysesCount = analyzed.length
  const atsValues = analyzed.map(f => f.atsScore).filter((v): v is number => v != null)
  const avgAts = atsValues.length
    ? Math.round(atsValues.reduce((sum, v) => sum + v, 0) / atsValues.length)
    : null
  const statValues: { val: string; sub: string }[] = [
    { val: String(recentFiles.length), sub: recentFiles.length ? "recent uploads" : "nothing uploaded yet" },
    { val: jobCount == null ? "…" : String(jobCount), sub: jobCount ? "saved for targeting" : "none saved yet" },
    { val: avgAts == null ? "N/A" : String(avgAts), sub: avgAts == null ? "analyze a resume first" : "across latest analyses" },
    { val: String(analysesCount), sub: analysesCount ? "latest per resume" : "no analyses yet" },
  ]

  const openReport = (f: RecentFile) => {
    if (!f.analysis) { addToast("error", "This resume has no analysis yet — run one from the Upload page."); return }
    api.saveLastAnalysis({ ...f.analysis, resume_id: f.id, report: f.analysis.report ?? {} })
    api.saveLastResumeId(f.id)
    api.saveLastResumeMeta(f.name, f.job === "General analysis" ? undefined : "Saved job description")
    navigate("analysis")
  }

  const exportResume = async (f: RecentFile) => {
    addToast("info", `Generating DOCX for ${f.name}…`)
    try {
      const blob = await api.exportResume(f.id)
      const link = document.createElement("a")
      link.href = URL.createObjectURL(blob)
      link.download = `${f.name.replace(/\.[^.]+$/, "")}_ATS_Optimized.docx`
      link.click()
      URL.revokeObjectURL(link.href)
      addToast("success", "ATS-optimized resume downloaded!")
    } catch (error) {
      addToast("error", error instanceof Error ? error.message : "Could not export resume")
    }
  }

  return (
    <div className="min-h-screen bg-warm">
      <div className="max-w-7xl mx-auto px-6 py-8">

        {/* Welcome */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <p className="text-mid text-sm mb-0.5">Good morning 👋</p>
            <h1 className="font-display font-bold text-2xl text-navy">{firstName ? `Welcome back, ${firstName}` : "Welcome back"}</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("jobs")}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-edge bg-surface text-navy text-sm font-medium hover:border-navy/30 hover:shadow-sm transition-all"
            >
              <Plus size={15} />
              Add Job Description
            </button>
            <button
              onClick={() => navigate("upload")}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-navy text-white text-sm font-semibold hover:bg-navy-light transition-all"
              style={{ boxShadow: "0 2px 8px rgba(27,42,74,0.2)" }}
            >
              <Upload size={15} />
              Upload New Resume
            </button>
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {statCardMeta.map((s, i) => (
            <div key={i} className="bg-surface rounded-2xl p-5 border border-edge hover:shadow-md transition-all duration-200">
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: s.iconBg }}>
                  <s.icon size={18} style={{ color: s.iconColor }} />
                </div>
                {s.isScore && avgAts != null && <MiniGauge score={avgAts} />}
              </div>
              <p className="font-code font-medium text-3xl text-navy mb-1">{statValues[i].val}</p>
              <p className="text-xs font-medium text-navy mb-0.5">{s.label}</p>
              <p className="text-xs text-dim">{statValues[i].sub}</p>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Recent files table */}
          <div className="lg:col-span-2 bg-surface rounded-2xl border border-edge overflow-hidden">
            <div className="px-6 py-4 border-b border-edge flex items-center justify-between">
              <h2 className="font-display font-semibold text-base text-navy">Recent Analyses</h2>
              <button
                onClick={() => navigate("upload")}
                className="text-xs text-teal font-medium hover:underline flex items-center gap-1"
              >
                View all <ChevronRight size={12} />
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-off">
                    <th className="px-6 py-3 text-left text-[11px] font-semibold text-mid uppercase tracking-wide">File</th>
                    <th className="px-3 py-3 text-left text-[11px] font-semibold text-mid uppercase tracking-wide">ATS Score</th>
                    <th className="px-3 py-3 text-left text-[11px] font-semibold text-mid uppercase tracking-wide">Keywords</th>
                    <th className="px-3 py-3 text-left text-[11px] font-semibold text-mid uppercase tracking-wide hidden md:table-cell">Target Job</th>
                    <th className="px-3 py-3 text-left text-[11px] font-semibold text-mid uppercase tracking-wide">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-edge">
                  {recentFiles.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-6 py-10 text-center">
                        <p className="text-sm text-mid mb-1">No resumes yet.</p>
                        <p className="text-xs text-dim">Upload your first resume to see analyses here.</p>
                      </td>
                    </tr>
                  )}
                  {recentFiles.map(f => (
                    <tr key={f.id} className="hover:bg-warm/60 transition-colors group">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <FileTypeBadge type={f.type} />
                          <div>
                            <p className="text-sm font-medium text-navy leading-none">{f.name}</p>
                            <p className="text-xs text-dim mt-0.5">{f.date}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-4">
                        <ScoreBadge score={f.atsScore} />
                      </td>
                      <td className="px-3 py-4">
                        <ScoreBadge score={f.kwScore} />
                      </td>
                      <td className="px-3 py-4 hidden md:table-cell">
                        <p className="text-xs text-mid max-w-[140px] truncate">{f.job}</p>
                      </td>
                      <td className="px-3 py-4">
                        <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => openReport(f)}
                            className="p-1.5 rounded-lg hover:bg-teal/10 text-mid hover:text-teal transition-colors"
                            title={f.analysis ? "View Report" : "No analysis yet"}
                          >
                            <ExternalLink size={13} />
                          </button>
                          <button
                            onClick={() => { api.saveLastResumeId(f.id); navigate("upload") }}
                            className="p-1.5 rounded-lg hover:bg-navy/10 text-mid hover:text-navy transition-colors"
                            title="Re-run analysis from the Upload page"
                          >
                            <RefreshCw size={13} />
                          </button>
                          <button
                            onClick={() => exportResume(f)}
                            className="p-1.5 rounded-lg hover:bg-teal/10 text-mid hover:text-teal transition-colors"
                            title="Export tailored DOCX"
                          >
                            <Download size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Sidebar */}
          <div className="flex flex-col gap-4">
            {/* Tip card */}
            <div className="bg-navy rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-teal/15 flex items-center justify-center">
                  <Lightbulb size={14} className="text-teal" />
                </div>
                <p className="text-white font-semibold text-sm">ATS Pro Tip</p>
              </div>
              <p className="text-white/60 text-sm leading-relaxed mb-4">{tips[tipIdx]}</p>
              <button
                onClick={() => setTipIdx((tipIdx + 1) % tips.length)}
                className="text-xs text-teal font-medium hover:underline"
              >
                Next tip →
              </button>
            </div>

            {/* Score trend */}
            <div className="bg-surface rounded-2xl border border-edge p-5">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp size={16} className="text-teal" />
                <p className="font-semibold text-navy text-sm">Score Progress</p>
              </div>
              <div className="space-y-3">
                {analyzed.slice().reverse().map(f => (
                  <div key={f.id}>
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs text-mid truncate max-w-[140px]">{f.name}</p>
                      <span className="text-xs font-code font-medium" style={{ color: (f.atsScore ?? 0) >= 75 ? "#00C9A7" : (f.atsScore ?? 0) >= 50 ? "#FFB800" : "#FF4757" }}>{f.atsScore ?? "N/A"}</span>
                    </div>
                    <div className="h-1.5 bg-off rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${f.atsScore ?? 0}%`,
                          background: (f.atsScore ?? 0) >= 75 ? "#00C9A7" : (f.atsScore ?? 0) >= 50 ? "#FFB800" : "#FF4757"
                        }}
                      />
                    </div>
                  </div>
                ))}
                {analyzed.length === 0 && <p className="text-xs text-dim">Run an analysis to track score progress.</p>}
              </div>
            </div>

            {/* Quick actions */}
            <div className="bg-surface rounded-2xl border border-edge p-5">
              <p className="font-semibold text-navy text-sm mb-3">Quick Actions</p>
              <div className="space-y-2">
                {[
                  { label: "View latest report", icon: BarChart2, action: () => navigate("analysis") },
                  { label: "Upload new resume",   icon: Upload,    action: () => navigate("upload") },
                  { label: "Add job description", icon: Briefcase, action: () => navigate("jobs") },
                ].map((a, i) => (
                  <button
                    key={i}
                    onClick={a.action}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-navy font-medium hover:bg-warm transition-all text-left"
                  >
                    <a.icon size={15} className="text-mid" />
                    {a.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
