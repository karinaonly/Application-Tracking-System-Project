import { ArrowRight, CheckCircle, Upload, FileSearch, Sparkles, Shield, BarChart2, Zap, Target, Edit3, Download, AlignLeft } from "lucide-react"
import type { Page } from "../types"

interface LandingProps {
  navigate: (p: Page) => void
}

function ScoreMockup() {
  return (
    <div className="relative w-full max-w-md mx-auto">
      <div
        className="rounded-2xl border border-white/10 overflow-hidden"
        style={{ background: "rgba(255,255,255,0.05)", backdropFilter: "blur(20px)", boxShadow: "0 32px 80px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.08)" }}
      >
        <div className="px-5 py-3 border-b border-white/10 flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red opacity-60" />
            <div className="w-3 h-3 rounded-full bg-amber opacity-60" />
            <div className="w-3 h-3 rounded-full bg-teal opacity-60" />
          </div>
          <span className="text-white/40 text-xs font-code ml-2">analysis_report.tsx</span>
        </div>
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-white/50 text-[11px] font-medium uppercase tracking-widest mb-1">Overall ATS Score</p>
              <p className="text-white font-display text-lg font-semibold">sample_resume.pdf</p>
            </div>
            <div className="relative w-20 h-20">
              <svg viewBox="0 0 80 80" className="w-full h-full">
                <circle cx="40" cy="40" r="32" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
                <circle
                  cx="40" cy="40" r="32"
                  fill="none"
                  stroke="#00C9A7"
                  strokeWidth="6"
                  strokeDasharray={`${2 * Math.PI * 32 * 0.72} ${2 * Math.PI * 32 * 0.28}`}
                  strokeLinecap="round"
                  transform="rotate(-90 40 40)"
                  style={{ filter: "drop-shadow(0 0 8px rgba(0,201,167,0.6))" }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-white font-code text-xl font-medium">72</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "ATS Compat", val: "68%", color: "#FFB800" },
              { label: "Keywords",   val: "58%", color: "#FF4757" },
              { label: "Bullets",    val: "71%", color: "#00C9A7" },
            ].map(s => (
              <div key={s.label} className="rounded-lg px-3 py-2.5" style={{ background: "rgba(255,255,255,0.06)" }}>
                <p className="text-white/40 text-[10px] font-medium mb-1">{s.label}</p>
                <p className="font-code font-medium text-sm" style={{ color: s.color }}>{s.val}</p>
              </div>
            ))}
          </div>

          <div className="space-y-1.5">
            <p className="text-white/40 text-[10px] font-medium uppercase tracking-widest">Missing Keywords</p>
            <div className="flex flex-wrap gap-1.5">
              {["Kubernetes", "gRPC", "Kafka", "Terraform", "distributed systems"].map(k => (
                <span key={k} className="text-[11px] px-2 py-0.5 rounded-full font-medium" style={{ background: "rgba(255,71,87,0.15)", color: "#FF7785", border: "1px solid rgba(255,71,87,0.3)" }}>{k}</span>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <p className="text-white/40 text-[10px] font-medium uppercase tracking-widest">Matched Keywords</p>
            <div className="flex flex-wrap gap-1.5">
              {["Python", "React", "Docker", "CI/CD", "PostgreSQL"].map(k => (
                <span key={k} className="text-[11px] px-2 py-0.5 rounded-full font-medium" style={{ background: "rgba(0,201,167,0.15)", color: "#00C9A7", border: "1px solid rgba(0,201,167,0.3)" }}>{k}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="absolute -top-4 -right-4 w-24 bg-surface rounded-xl p-3 shadow-xl border border-edge rotate-3">
        <p className="text-[10px] text-mid font-medium">Bullet Rewrite</p>
        <p className="text-[10px] text-navy mt-1 font-medium leading-tight">"Helped" → <span className="text-teal">"Engineered"</span></p>
      </div>

      <div className="absolute -bottom-4 -left-4 bg-surface rounded-xl px-3 py-2.5 shadow-xl border border-edge -rotate-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-[rgba(0,201,167,0.1)] flex items-center justify-center">
            <CheckCircle size={12} className="text-teal" />
          </div>
          <div>
            <p className="text-[10px] font-semibold text-navy">ATS-Ready export</p>
            <p className="text-[9px] text-mid">Download optimized DOCX</p>
          </div>
        </div>
      </div>
    </div>
  )
}

const features = [
  {
    icon: Shield,
    title: "ATS Compatibility Scoring",
    desc: "Detects tables, headers/footers, non-standard fonts, and missing sections that confuse ATS parsers.",
    color: "#3B82F6",
    bg: "rgba(59,130,246,0.1)",
  },
  {
    icon: Target,
    title: "Keyword Gap Analysis",
    desc: "NLP-powered matching compares your resume against any job description to surface critical missing keywords.",
    color: "#8B5CF6",
    bg: "rgba(139,92,246,0.1)",
  },
  {
    icon: BarChart2,
    title: "Bullet Point Scoring",
    desc: "Analyzes action verb strength, quantifiable metrics, and specificity for every bullet in your resume.",
    color: "#00C9A7",
    bg: "rgba(0,201,167,0.1)",
  },
  {
    icon: Sparkles,
    title: "AI-Powered Rewrites",
    desc: "Moderate and aggressive rewrite suggestions turn weak bullets into clearer achievements — and nothing is applied until you approve it.",
    color: "#F59E0B",
    bg: "rgba(245,158,11,0.1)",
  },
  {
    icon: AlignLeft,
    title: "Grammar & Spell Check",
    desc: "Tech-term-aware spell checker flags typos while respecting industry jargon like APIs and microservices.",
    color: "#EC4899",
    bg: "rgba(236,72,153,0.1)",
  },
  {
    icon: Download,
    title: "One-Click ATS Export",
    desc: "Download a clean, ATS-optimized DOCX with proper heading styles, single-column layout, and no tables.",
    color: "#06B6D4",
    bg: "rgba(6,182,212,0.1)",
  },
]

const steps = [
  {
    n: "01",
    icon: Upload,
    title: "Upload Your Resume",
    desc: "Drag and drop your resume in PDF, DOCX, or TXT format — up to 10MB. We parse it instantly.",
  },
  {
    n: "02",
    icon: FileSearch,
    title: "Add a Job Description",
    desc: "Paste the job posting directly, or import it from a public URL. If a site blocks automated access, paste the text instead.",
  },
  {
    n: "03",
    icon: Sparkles,
    title: "Get Instant AI Analysis",
    desc: "Receive your ATS score, keyword gap report, bullet improvements, and one-click export in seconds.",
  },
]

export default function Landing({ navigate }: LandingProps) {
  return (
    <div className="min-h-screen">
      {/* Top nav */}
      <header className="absolute top-0 left-0 right-0 z-30">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center backdrop-blur-sm">
              <Zap size={16} className="text-teal" fill="#00C9A7" />
            </div>
            <span className="font-display font-bold text-white text-[15px] tracking-tight">
              ResumeATS <span className="text-teal">Pro</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate("login")}
              className="px-4 py-2 text-sm font-medium text-white/80 hover:text-white transition-colors"
            >
              Sign In
            </button>
            <button
              onClick={() => navigate("register")}
              className="px-4 py-2 bg-teal text-navy text-sm font-semibold rounded-lg hover:bg-teal-dim transition-all"
              style={{ boxShadow: "0 0 20px rgba(0,201,167,0.3)" }}
            >
              Get Started
            </button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section
        className="relative min-h-screen flex items-center pt-16 overflow-hidden"
        style={{ background: "linear-gradient(135deg, #0F1C33 0%, #1B2A4A 50%, #1A3055 100%)" }}
      >
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 -left-40 w-96 h-96 rounded-full opacity-10" style={{ background: "radial-gradient(circle, #00C9A7, transparent)" }} />
          <div className="absolute bottom-1/4 -right-40 w-96 h-96 rounded-full opacity-10" style={{ background: "radial-gradient(circle, #334d80, transparent)" }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full opacity-5" style={{ background: "radial-gradient(circle, #00C9A7, transparent)" }} />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 py-24 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-6 text-xs font-medium text-teal" style={{ background: "rgba(0,201,167,0.1)", border: "1px solid rgba(0,201,167,0.2)" }}>
              <Sparkles size={12} />
              AI-Powered Resume Optimization
            </div>
            <h1 className="font-display font-extrabold text-5xl lg:text-6xl text-white leading-[1.1] tracking-tight mb-6">
              Stop Getting{" "}
              <span className="text-teal" style={{ textShadow: "0 0 40px rgba(0,201,167,0.4)" }}>Rejected</span>{" "}
              by Robots.
            </h1>
            <p className="text-white/60 text-lg leading-relaxed mb-8 max-w-lg">
              Most resumes are rejected by ATS software before a human ever reads them. ResumeATS Pro analyzes your resume against any job description and gives you an exact roadmap to pass through.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 mb-10">
              <button
                onClick={() => navigate("register")}
                className="flex items-center justify-center gap-2 px-6 py-3.5 bg-teal text-navy font-semibold rounded-xl text-sm hover:bg-teal-dim transition-all group"
                style={{ boxShadow: "0 0 30px rgba(0,201,167,0.35)" }}
              >
                Analyze My Resume
                <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
              <button
                onClick={() => navigate("login")}
                className="flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl text-sm font-medium text-white/70 hover:text-white transition-all"
                style={{ border: "1px solid rgba(255,255,255,0.12)", background: "rgba(255,255,255,0.04)" }}
              >
                Sign In
              </button>
            </div>
            <div className="flex items-center gap-6">
              {[
                { val: "3", label: "Upload formats" },
                { val: "2", label: "Export formats" },
                { val: "Opt-in", label: "AI rewrites" },
              ].map(s => (
                <div key={s.label}>
                  <p className="font-display font-bold text-xl text-white">{s.val}</p>
                  <p className="text-white/40 text-xs">{s.label}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <ScoreMockup />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-24 bg-surface">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <p className="text-teal text-sm font-semibold uppercase tracking-widest mb-3">How It Works</p>
            <h2 className="font-display font-bold text-4xl text-navy">Three steps to ATS clarity</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            <div className="hidden md:block absolute top-10 left-1/3 right-1/3 h-px border-t-2 border-dashed border-edge" />
            {steps.map((s, i) => (
              <div key={i} className="relative">
                <div className="flex flex-col items-center text-center p-8 rounded-2xl bg-warm border border-edge hover:border-teal/30 transition-all duration-300 hover:shadow-md">
                  <div className="relative mb-6">
                    <div className="w-14 h-14 rounded-2xl bg-navy flex items-center justify-center">
                      <s.icon size={22} className="text-teal" />
                    </div>
                    <span className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-teal flex items-center justify-center text-navy text-[10px] font-bold font-code">{i + 1}</span>
                  </div>
                  <h3 className="font-display font-bold text-lg text-navy mb-2">{s.title}</h3>
                  <p className="text-mid text-sm leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 bg-warm">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <p className="text-teal text-sm font-semibold uppercase tracking-widest mb-3">Features</p>
            <h2 className="font-display font-bold text-4xl text-navy mb-4">Everything your resume needs</h2>
            <p className="text-mid max-w-lg mx-auto">A complete AI-powered toolkit built for job seekers who are serious about landing interviews.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((f, i) => (
              <div
                key={i}
                className="p-6 bg-surface rounded-2xl border border-edge hover:border-[rgba(0,201,167,0.2)] transition-all duration-300 hover:shadow-lg group cursor-default"
              >
                <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4 transition-transform duration-200 group-hover:scale-110" style={{ background: f.bg }}>
                  <f.icon size={20} style={{ color: f.color }} />
                </div>
                <h3 className="font-display font-semibold text-base text-navy mb-2">{f.title}</h3>
                <p className="text-mid text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="py-16 bg-navy">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              { val: "3",       label: "Upload Formats", sub: "PDF, DOCX, and TXT" },
              { val: "2",       label: "Export Formats", sub: "clean DOCX and PDF" },
              { val: "100%",    label: "Rewrite Review", sub: "nothing applied without approval" },
              { val: "Opt-in",  label: "AI Usage", sub: "off until you enable it" },
            ].map(s => (
              <div key={s.label} className="text-center">
                <p className="font-display font-extrabold text-4xl text-teal mb-1" style={{ textShadow: "0 0 20px rgba(0,201,167,0.3)" }}>{s.val}</p>
                <p className="text-white font-semibold text-sm mb-0.5">{s.label}</p>
                <p className="text-white/40 text-xs">{s.sub}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA section */}
      <section className="py-24 bg-surface">
        <div className="max-w-2xl mx-auto px-6 text-center">
          <div className="w-14 h-14 rounded-2xl bg-navy flex items-center justify-center mx-auto mb-6">
            <Zap size={24} className="text-teal" fill="#00C9A7" />
          </div>
          <h2 className="font-display font-bold text-4xl text-navy mb-4">Your next job starts with a better resume</h2>
          <p className="text-mid leading-relaxed mb-8">Upload a resume, compare it against a job description, and see exactly which keywords and bullets need work. Every AI suggestion waits for your approval before it touches your resume.</p>
          <button
            onClick={() => navigate("register")}
            className="inline-flex items-center gap-2 px-8 py-4 bg-teal text-navy font-bold rounded-xl text-sm hover:bg-teal-dim transition-all group"
            style={{ boxShadow: "0 0 30px rgba(0,201,167,0.3)" }}
          >
            Create an Account
            <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
          </button>
          <p className="text-dim text-xs mt-4">AI rewriting is off by default and stays off until you enable it.</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 bg-navy border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-teal" fill="#00C9A7" />
            <span className="text-white/60 text-sm font-display font-semibold">ResumeATS Pro</span>
          </div>
          <p className="text-white/30 text-xs">© 2026 ResumeATS Pro. ATS resume analysis with reviewable suggestions.</p>
          <span className="text-white/20 text-xs font-code">v1.0</span>
        </div>
      </footer>
    </div>
  )
}
