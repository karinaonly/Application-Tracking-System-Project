const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000"

export interface User {
  id: string
  email: string
  full_name: string
  created_at: string
}

export interface JobDescription {
  id: string
  title: string
  company: string | null
  raw_text: string
  url: string | null
  created_at: string
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
      reason?: string | null
      similarity?: number | null
      keyword_details?: Array<{ skill: string; jd_mentions: number; in_resume: boolean }>
      other_terms_missing?: string[]
      matched_keywords?: string[]
      missing_keywords?: string[]
    }
    grammar?: { typos_found?: Array<{ word: string; suggestion: string }> }
    ai_rewritten_examples?: Record<string, string | { moderate?: string; aggressive?: string; ai_output?: string; source?: string; error?: string; guard?: { status: string; reasons: string[]; retried: boolean; rejected_variants?: string[] } }>
    overall_score?: number
    weights_used?: Record<string, number>
  }
  created_at: string
}

export interface AIStatus {
  configured: boolean
  model: string
  provider?: string
  reason?: "configured" | "missing" | "invalid_format" | "quota_exhausted" | "model_unavailable"
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

export async function listResumes(): Promise<ResumeSummary[]> {
  return request<ResumeSummary[]>("/resumes/")
}

export async function uploadResume(file: File): Promise<{ id: string; filename: string; status: string }> {
  const formData = new FormData()
  formData.append("file", file)
  return request<{ id: string; filename: string; status: string }>("/resumes/upload", { method: "POST", body: formData })
}

export async function analyzeResume(resumeId: string, jobId?: string): Promise<ResumeAnalysis> {
  const query = jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""
  return request<ResumeAnalysis>(`/resumes/${resumeId}/analyze${query}`, { method: "POST" })
}

export async function exportResume(resumeId: string, analysisId?: string): Promise<Blob> {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)
  // A18: export the analysis being viewed, not "the latest" server-side.
  const query = analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : ""
  const response = await fetch(`${API_BASE_URL}/resumes/${resumeId}/export${query}`, { headers })
  if (!response.ok) throw new Error("Could not export resume")
  return response.blob()
}

export function saveLastAnalysis(analysis: ResumeAnalysis): void {
  sessionStorage.setItem("ats_last_analysis", JSON.stringify(analysis))
}

export function getLastAnalysis(): ResumeAnalysis | null {
  const raw = sessionStorage.getItem("ats_last_analysis")
  if (!raw) return null
  try { return JSON.parse(raw) as ResumeAnalysis } catch { return null }
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
