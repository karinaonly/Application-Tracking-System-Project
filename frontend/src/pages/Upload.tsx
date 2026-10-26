import { useEffect, useState, useRef } from "react"
import { Upload as UploadIcon, FileText, Trash2, BarChart2, Download, CheckCircle, AlertCircle, Plus } from "lucide-react"
import type { PageProps } from "../types"
import * as api from "../api"

function FileTypeBadge({ type }: { type: string }) {
  const s: Record<string, { bg: string; color: string }> = {
    PDF:  { bg: "rgba(239,68,68,0.1)",  color: "#EF4444" },
    DOCX: { bg: "rgba(59,130,246,0.1)", color: "#3B82F6" },
    TXT:  { bg: "rgba(107,114,128,0.1)", color: "#6B7280" },
  }
  const c = s[type] ?? s.TXT
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-code font-semibold uppercase" style={c}>{type}</span>
  )
}

function ScorePip({ score }: { score: number }) {
  const color = score >= 75 ? "#00C9A7" : score >= 50 ? "#FFB800" : "#FF4757"
  return (
    <span className="font-code font-medium text-sm" style={{ color }}>{score}</span>
  )
}

export default function UploadPage({ navigate, addToast }: PageProps) {
  const [dragging, setDragging] = useState(false)
  const [uploaded, setUploaded] = useState<{ id: string; name: string; type: string; size: string } | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [jobs, setJobs] = useState<api.JobDescription[]>([])
  const [resumes, setResumes] = useState<api.ResumeSummary[]>([])
  const [selectedJobId, setSelectedJobId] = useState<string>()
  const inputRef = useRef<HTMLInputElement>(null)
  const activeJobId = selectedJobId ?? jobs[0]?.id

  useEffect(() => {
    Promise.all([api.listJobs(), api.listResumes()]).then(([loadedJobs, loadedResumes]) => {
      setJobs(loadedJobs); setResumes(loadedResumes)
    }).catch(error => addToast("error", error.message))
  }, [addToast])

  const handleFile = async (file: File) => {
    const ext = file.name.split(".").pop()?.toUpperCase() ?? "PDF"
    const size = file.size < 1024 * 1024 ? `${Math.round(file.size / 1024)} KB` : `${(file.size / (1024 * 1024)).toFixed(1)} MB`
    if (file.size > 10 * 1024 * 1024) { addToast("error", "File too large. Maximum size is 10 MB."); return }
    try {
      const result = await api.uploadResume(file)
      setUploaded({ id: result.id, name: file.name, type: ext, size })
      setResumes(await api.listResumes())
      addToast("success", `${file.name} uploaded successfully!`)
    } catch (error) { addToast("error", error instanceof Error ? error.message : "Could not upload resume") }
  }

  const handleAnalyze = async () => {
    if (!uploaded) return
    setAnalyzing(true)
    addToast("info", "Analyzing your resume against the selected job description…")
    try {
      const analysis = await api.analyzeResume(uploaded.id, activeJobId)
      api.saveLastAnalysis(analysis); api.saveLastResumeId(uploaded.id)
      api.saveLastResumeMeta(uploaded.name, jobs.find(job => job.id === activeJobId)?.title)
      navigate("analysis")
    } catch (error) { addToast("error", error instanceof Error ? error.message : "Could not analyze resume") }
    finally { setAnalyzing(false) }
  }

  return (
    <div className="min-h-screen bg-warm">
      <div className="max-w-4xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="font-display font-bold text-2xl text-navy mb-1">My Resumes</h1>
          <p className="text-mid text-sm">Upload your resume and run an ATS analysis against any saved job description.</p>
        </div>

        {/* Upload zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f) }}
          onClick={() => !uploaded && inputRef.current?.click()}
          className={`relative rounded-2xl border-2 border-dashed p-12 mb-6 transition-all duration-200 cursor-pointer ${
            dragging
              ? "border-teal bg-[rgba(0,201,167,0.06)] scale-[1.01]"
              : uploaded
              ? "border-teal bg-[rgba(0,201,167,0.04)] cursor-default"
              : "border-edge bg-surface hover:border-navy/30 hover:bg-off/50"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept=".pdf,.docx,.txt"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
          />
          {!uploaded ? (
            <div className="flex flex-col items-center text-center">
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-all ${dragging ? "bg-teal/20" : "bg-off"}`}>
                <UploadIcon size={26} className={dragging ? "text-teal" : "text-mid"} />
              </div>
              <p className="font-display font-semibold text-navy text-lg mb-1.5">
                {dragging ? "Drop your resume here" : "Drag & drop your resume"}
              </p>
              <p className="text-mid text-sm mb-4">or click to browse your files</p>
              <div className="flex items-center gap-2">
                {["PDF", "DOCX", "TXT"].map(t => <FileTypeBadge key={t} type={t} />)}
                <span className="text-xs text-dim">· Max 10 MB</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-5">
              <div className="w-16 h-16 rounded-2xl bg-teal/10 flex items-center justify-center shrink-0">
                <CheckCircle size={28} className="text-teal" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-display font-semibold text-navy">{uploaded.name}</p>
                  <FileTypeBadge type={uploaded.type} />
                </div>
                <p className="text-mid text-sm">{uploaded.size} · Uploaded just now</p>
                <div className="flex items-center gap-1 mt-1.5">
                  <CheckCircle size={12} className="text-teal" />
                  <p className="text-xs text-teal font-medium">Resume parsed successfully — ready for analysis</p>
                </div>
              </div>
              <button
                onClick={e => { e.stopPropagation(); setUploaded(null) }}
                className="p-2 rounded-lg hover:bg-red/10 text-dim hover:text-red transition-colors"
              >
                <Trash2 size={16} />
              </button>
            </div>
          )}
        </div>

        {/* Job description selector + analyze */}
        {uploaded && (
          <div className="bg-surface rounded-2xl border border-edge p-5 mb-6">
            <p className="font-semibold text-navy text-sm mb-4">Select a Job Description to Analyze Against</p>
            <div className="grid gap-2 mb-4">
              {jobs.map((j) => (
                <label key={j.id} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${activeJobId === j.id ? "border-teal bg-teal/5" : "border-edge hover:border-navy/20"}`}>
                  <input type="radio" name="job" className="sr-only" checked={activeJobId === j.id} onChange={() => setSelectedJobId(j.id)} />
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-colors ${activeJobId === j.id ? "border-teal" : "border-edge"}`}>
                    {activeJobId === j.id && <div className="w-2 h-2 rounded-full bg-teal" />}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-navy">{j.title}</p>
                    <p className="text-xs text-mid">{j.company || "Company not provided"}</p>
                  </div>
                </label>
              ))}
            </div>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="flex items-center gap-2 px-5 py-2.5 bg-teal text-navy font-semibold text-sm rounded-xl hover:bg-teal-dim transition-all disabled:opacity-70"
              style={{ boxShadow: "0 2px 12px rgba(0,201,167,0.25)" }}
            >
              {analyzing ? (
                <><div className="w-4 h-4 border-2 border-navy/30 border-t-navy rounded-full animate-spin" /> Analyzing…</>
              ) : (
                <><BarChart2 size={15} /> Proceed to Analysis</>
              )}
            </button>
          </div>
        )}

        {/* ATS formatting tips */}
        <div className="bg-[rgba(255,184,0,0.06)] border border-[rgba(255,184,0,0.2)] rounded-2xl p-4 mb-8 flex items-start gap-3">
          <AlertCircle size={16} className="text-amber mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-navy mb-1">Before you upload</p>
            <p className="text-xs text-mid leading-relaxed">For best ATS parsing results, ensure your resume uses a single-column layout, standard fonts, and no tables, text boxes, or headers/footers. PDFs exported from Word or Google Docs work best.</p>
          </div>
        </div>

        {/* Past resumes */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display font-semibold text-base text-navy">Previous Uploads</h2>
            <button
              onClick={() => inputRef.current?.click()}
              className="flex items-center gap-1.5 text-xs text-teal font-medium hover:underline"
            >
              <Plus size={13} /> Upload another
            </button>
          </div>
          <div className="space-y-3">
            {resumes.map((r) => (
              <div key={r.id} className="bg-surface rounded-xl border p-4 flex items-center gap-4 hover:border-navy/20 hover:shadow-sm transition-all group">
                <div className="w-10 h-10 rounded-xl bg-off flex items-center justify-center shrink-0">
                  <FileText size={18} className="text-mid" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <p className="font-medium text-navy text-sm truncate">{r.filename}</p>
                    <FileTypeBadge type={r.file_type} />
                  </div>
                    <p className="text-xs text-dim">{new Date(r.created_at).toLocaleDateString()}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  {r.latest_analysis && <span className="text-xs text-mid mr-2 hidden sm:block">ATS: <ScorePip score={r.latest_analysis.ats_score} /></span>}
                  <button
                    onClick={() => { if (r.latest_analysis) { api.saveLastResumeId(r.id); navigate("analysis") } else addToast("info", "Analyze this resume first") }}
                    className="p-2 rounded-lg text-mid hover:text-teal hover:bg-teal/10 transition-colors"
                    title="View Analysis"
                  >
                    <BarChart2 size={15} />
                  </button>
                  <button
                    onClick={async () => { try { const blob = await api.exportResume(r.id); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = r.filename; link.click(); URL.revokeObjectURL(link.href) } catch (error) { addToast("error", error instanceof Error ? error.message : "Could not export resume") } }}
                    className="p-2 rounded-lg text-mid hover:text-navy hover:bg-off transition-colors"
                    title="Download"
                  >
                    <Download size={15} />
                  </button>
                  <button
                    onClick={() => addToast("info", "Resume deletion is not available in the backend yet.")}
                    className="p-2 rounded-lg text-dim hover:text-red hover:bg-red/10 transition-colors opacity-0 group-hover:opacity-100"
                    title="Delete"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
