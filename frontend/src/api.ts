const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000"

export interface User {
  id: string
  email: string
  full_name: string
  created_at: string
}

// D2: structured JD parse stored on save (required/preferred skills, tools,
// seniority). Absent or empty for jobs saved before the parser existed.
export interface ExtractedKeywords {
  required_skills: string[]
  preferred_skills: string[]
  other_skills: string[]
  tools: string[]
  seniority: string
  min_years_experience: number | null
}

// D7: one status per saved job. Dates and notes are optional and never guessed.
export type ApplicationStatus = "saved" | "applied" | "interview" | "offer" | "rejected"

export interface JobDescription {
  id: string
  title: string
  company: string | null
  raw_text: string
  url: string | null
  extracted_keywords?: ExtractedKeywords
  application_status?: ApplicationStatus
  applied_at?: string | null
  notes?: string
  created_at: string
}

export interface JobApplicationUpdate {
  status?: ApplicationStatus
  // null clears the date; omitting the field leaves it untouched.
  applied_at?: string | null
  notes?: string
}

export interface ResumeSummary {
  id: string
  filename: string
  file_type: string
  created_at: string
  latest_analysis: {
    id: string
    overall_score: number
    ats_score: number
    keyword_score: number
    bullet_score: number
    job_id: string | null
    created_at: string
    report?: ResumeAnalysis["report"]
  } | null
  // D3: tailored versions stored for this resume (absent in older responses)
  versions?: ResumeVersionSummary[]
}

// D3: a stored tailored version of a resume for a specific job
export interface ResumeVersionSummary {
  id: string
  job_id: string | null
  label: string
  applied_rewrites_count: number
  created_at: string
}

export interface ResumeAnalysis {
  id: string
  resume_id: string
  job_id: string | null
  overall_score: number
  ats_score: number
  keyword_score: number
  bullet_score: number
  report: {
    ats?: {
      issues?: Array<{ category: "critical" | "warning"; issue: string; fix: string }>
      passed?: string[]
    }
    bullet_analysis?: {
      score?: number | null
      score_available?: boolean
      warning?: string | null
      total_bullets?: number
      bullets_with_metrics?: number
      strong_verbs_count?: number
      weak_verbs_count?: number
      details?: Array<{
        original: string
        section?: string
        verb_type: "strong" | "weak" | "missing"
        has_metrics: boolean
        metrics: string[]
        suggestion: string
      }>
    }
    keyword_analysis?: {
      score?: number | null
      score_available?: boolean
      // B8: true when required/preferred buckets from the job parser were
      // used to weight the score (required 3x, preferred 2x).
      weighted?: boolean
      reason?: string | null
      keyword_details?: Array<{
        skill: string
        jd_mentions: number
        in_resume: boolean
        importance?: "required" | "preferred" | "other"
      }>
      other_terms_missing?: string[]
      matched_keywords?: string[]
      missing_keywords?: string[]
      // A3: subset of missing_keywords that are soft skills — shown as advice
      // only, never added to the exported Skills section.
      soft_missing_keywords?: string[]
    }
    // A3: missing keywords the user confirmed they actually have; only
    // these are injected into the exported resume's Skills section.
    confirmed_keywords?: string[]
    // C6: the user's review of each AI rewrite. Only "accepted" entries are
    // applied to the export; a fresh analysis has none.
    rewrite_decisions?: Record<string, { action: "accepted" | "rejected"; text?: string }>
    grammar?: { score?: number; typos_found?: Array<{ word: string; suggestion: string }> }
    ai_rewritten_examples?: Record<string, string | { moderate?: string; aggressive?: string; ai_output?: string; source?: string; error?: string; guard?: { status: string; reasons: string[]; retried: boolean; rejected_variants?: string[] } }>
    // E4: what happened to the AI step. `reason` is "ran", "disabled_by_user",
    // "disabled_by_server", "not_configured", or "no_flagged_bullets".
    ai_rewriting?: {
      enabled: boolean
      reason: "ran" | "disabled_by_user" | "disabled_by_server" | "not_configured" | "no_flagged_bullets"
      flagged_bullets: number
      bullets_sent: number
      provider: string | null
      model: string | null
    }
    overall_score?: number
    weights_used?: Record<string, number>
    // D1: before/after re-scoring of the AI-tailored bullets. Absent when no
    // rewrite changed a bullet (nothing to compare).
    improvement?: {
      applied_rewrites: number
      flagged_bullets: number
      before: { overall: number; bullets: number | null; keywords: number | null; grammar?: number | null }
      after: { overall: number; bullets: number | null; keywords: number | null; grammar?: number | null }
    }
  }
  created_at: string
}

export interface AIStatus {
  configured: boolean
  model: string
  provider?: string
  reason?: "configured" | "missing" | "invalid_format" | "quota_exhausted" | "model_unavailable"
  // E4: false means the server will never send resume text to the provider.
  rewriting_enabled?: boolean
}

// E3: non-secret switches available before sign-in.
export interface PublicConfig {
  registration_enabled: boolean
  ai_rewriting_enabled: boolean
}

export async function getPublicConfig(): Promise<PublicConfig> {
  return request<PublicConfig>("/auth/config")
}

interface TokenResponse {
  access_token: string
  token_type: string
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = getToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)
  if (!(options.body instanceof FormData) && options.body) headers.set("Content-Type", "application/json")

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function getToken(): string | null {
  return localStorage.getItem("ats_access_token")
}

export function setToken(token: string): void {
  localStorage.setItem("ats_access_token", token)
}

export function clearToken(): void {
  localStorage.removeItem("ats_access_token")
}

// E4: the AI-rewriting choice belongs to the person at this browser, so it is
// a local preference rather than an account setting. Default is on (the app's
// main feature); turning it off keeps every analysis on this machine.
const AI_PREFERENCE_KEY = "ats_ai_rewriting_enabled"

export function getAiRewritingPreference(): boolean {
  const stored = localStorage.getItem(AI_PREFERENCE_KEY)
  return stored === null ? true : stored === "true"
}

export function setAiRewritingPreference(enabled: boolean): void {
  localStorage.setItem(AI_PREFERENCE_KEY, enabled ? "true" : "false")
}

export async function register(data: { email: string; password: string; full_name: string }): Promise<User> {
  return request<User>("/auth/register", { method: "POST", body: JSON.stringify(data) })
}

export async function login(data: { email: string; password: string }): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) })
}

export async function getMe(): Promise<User> {
  return request<User>("/auth/me")
}

export async function updateMe(data: { full_name: string }): Promise<User> {
  return request<User>("/auth/me", { method: "PATCH", body: JSON.stringify(data) })
}

export async function changePassword(data: { current_password: string; new_password: string }): Promise<void> {
  return request<void>("/auth/change-password", { method: "POST", body: JSON.stringify(data) })
}

export async function getAIStatus(): Promise<AIStatus> {
  return request<AIStatus>("/auth/ai-status")
}

export async function listJobs(): Promise<JobDescription[]> {
  return request<JobDescription[]>("/jobs/")
}

export async function createJob(data: { title: string; company?: string; raw_text: string; url?: string }): Promise<JobDescription> {
  return request<JobDescription>("/jobs/", { method: "POST", body: JSON.stringify(data) })
}

export async function scrapeJob(url: string): Promise<JobDescription> {
  return request<JobDescription>("/jobs/from-url", { method: "POST", body: JSON.stringify({ url }) })
}

export async function updateJobApplication(jobId: string, data: JobApplicationUpdate): Promise<JobDescription> {
  return request<JobDescription>(`/jobs/${jobId}/application`, { method: "PATCH", body: JSON.stringify(data) })
}

export function saveSelectedJobId(id: string): void {
  sessionStorage.setItem("ats_selected_job_id", id)
}

export function getSelectedJobId(): string | null {
  return sessionStorage.getItem("ats_selected_job_id")
}

export async function listResumes(): Promise<ResumeSummary[]> {
  return request<ResumeSummary[]>("/resumes/")
}

export async function uploadResume(file: File): Promise<{ id: string; filename: string; status: string }> {
  const formData = new FormData()
  formData.append("file", file)
  return request<{ id: string; filename: string; status: string }>("/resumes/upload", { method: "POST", body: formData })
}

export async function analyzeResume(resumeId: string, jobId?: string, useAi = true): Promise<ResumeAnalysis> {
  const params = new URLSearchParams()
  if (jobId) params.set("job_id", jobId)
  // E4: the local analysis always runs; this only controls whether bullet
  // text may be sent to the AI provider.
  params.set("use_ai", useAi ? "true" : "false")
  return request<ResumeAnalysis>(`/resumes/${resumeId}/analyze?${params.toString()}`, { method: "POST" })
}

export async function exportResume(
  resumeId: string,
  analysisId?: string,
  // A4: opt-in only. By default the export keeps the resume's own title; set
  // this to true only when the user explicitly asks to match the job's title.
  matchTitle = false,
  // D5: both formats use the same tailored content.
  format: "docx" | "pdf" = "docx"
): Promise<Blob> {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)
  // A18: export the analysis being viewed, not "the latest" server-side.
  const params = new URLSearchParams()
  if (analysisId) params.set("analysis_id", analysisId)
  if (matchTitle) params.set("match_title", "true")
  params.set("format", format)
  const query = params.toString() ? `?${params.toString()}` : ""
  const response = await fetch(`${API_BASE_URL}/resumes/${resumeId}/export${query}`, { headers })
  if (!response.ok) throw new Error("Could not export resume")
  return response.blob()
}

// D3: per-job tailored resume versions
export async function createVersion(resumeId: string, analysisId: string): Promise<ResumeVersionSummary> {
  return request<ResumeVersionSummary>(`/resumes/${resumeId}/versions`, {
    method: "POST",
    body: JSON.stringify({ analysis_id: analysisId }),
  })
}

// A3: confirm which missing keywords the user actually has — only these
// are added to the exported resume's Skills section.
export async function confirmKeywords(
  resumeId: string,
  analysisId: string,
  keywords: string[]
): Promise<{ confirmed_keywords: string[]; soft_skipped?: string[] }> {
  return request<{ confirmed_keywords: string[]; soft_skipped?: string[] }>(
    `/resumes/${resumeId}/analyses/${analysisId}/confirm-keywords`,
    { method: "POST", body: JSON.stringify({ keywords }) }
  )
}

// C6: review AI rewrites. `pending` clears a previous decision so the card is
// unreviewed again. Only accepted rewrites reach the exported document.
export async function saveRewriteDecisions(
  resumeId: string,
  analysisId: string,
  decisions: Array<{ original: string; action: "accepted" | "rejected" | "pending"; text?: string }>
): Promise<{
  rewrite_decisions: Record<string, { action: "accepted" | "rejected"; text?: string }>
  applied: number
}> {
  return request<{
    rewrite_decisions: Record<string, { action: "accepted" | "rejected"; text?: string }>
    applied: number
  }>(`/resumes/${resumeId}/analyses/${analysisId}/rewrite-decisions`, {
    method: "POST",
    body: JSON.stringify({ decisions }),
  })
}

export async function listVersions(resumeId: string): Promise<ResumeVersionSummary[]> {  return request<ResumeVersionSummary[]>(`/resumes/${resumeId}/versions`)
}

export async function exportVersion(
  resumeId: string,
  versionId: string,
  // A4: same opt-in rule as exportResume.
  matchTitle = false,
  // D5: both formats use the same stored tailored content.
  format: "docx" | "pdf" = "docx"
): Promise<Blob> {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)
  const params = new URLSearchParams()
  if (matchTitle) params.set("match_title", "true")
  params.set("format", format)
  const response = await fetch(`${API_BASE_URL}/resumes/${resumeId}/versions/${versionId}/export?${params.toString()}`, { headers })
  if (!response.ok) throw new Error("Could not export version")
  return response.blob()
}

// F8: the Analysis page stores only ids and reloads the report from the API,
// so a refresh keeps the same analysis instead of trusting a serialized copy.
export async function getAnalysis(resumeId: string, analysisId: string): Promise<ResumeAnalysis> {
  return request<ResumeAnalysis>(`/resumes/${resumeId}/analyses/${analysisId}`)
}

// D6: original vs. tailored content, flattened into heading + display lines.
export interface ComparisonHeader {
  name: string
  title: string
  contact: string[]
}

export interface ComparisonSection {
  key: string
  heading: string
  lines: string[]
}

export interface ComparisonView {
  header: ComparisonHeader
  sections: ComparisonSection[]
}

export interface ComparisonChange {
  original: string
  tailored: string
}

export interface ResumeComparison {
  resume_id: string
  analysis_id: string
  job_title: string | null
  original: ComparisonView
  tailored: ComparisonView
  changes: ComparisonChange[]
  confirmed_keywords: string[]
}

export async function getComparison(resumeId: string, analysisId: string): Promise<ResumeComparison> {
  return request<ResumeComparison>(`/resumes/${resumeId}/analyses/${analysisId}/comparison`)
}

export function saveLastAnalysisId(id: string): void {
  sessionStorage.setItem("ats_last_analysis_id", id)
}

export function getLastAnalysisId(): string | null {
  return sessionStorage.getItem("ats_last_analysis_id")
}

export function saveLastResumeId(id: string): void {
  sessionStorage.setItem("ats_last_resume_id", id)
}

export function getLastResumeId(): string | null {
  return sessionStorage.getItem("ats_last_resume_id")
}

export function saveLastResumeMeta(filename: string, jobTitle?: string): void {
  sessionStorage.setItem("ats_last_resume_meta", JSON.stringify({ filename, jobTitle: jobTitle ?? "General analysis" }))
}

export function getLastResumeMeta(): { filename: string; jobTitle: string } | null {
  const raw = sessionStorage.getItem("ats_last_resume_meta")
  if (!raw) return null
  try { return JSON.parse(raw) as { filename: string; jobTitle: string } } catch { return null }
}
