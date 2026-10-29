import { useEffect, useState } from "react"
import { Eye, EyeOff, ArrowRight, CheckCircle, Zap, ArrowLeft } from "lucide-react"
import type { Page } from "../types"
import * as api from "../api"

interface AuthProps {
  mode: "login" | "register"
  navigate: (p: Page) => void
  onLogin: (token: string) => void
}

function InputField({
  label, type = "text", value, onChange, placeholder, error, helper
}: {
  label: string
  type?: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  error?: string
  helper?: string
}) {
  const [show, setShow] = useState(false)
  const isPass = type === "password"
  const inputType = isPass ? (show ? "text" : "password") : type
  const hasError = !!error
  const isValid = value.length > 0 && !error

  return (
    <div>
      <label className="block text-sm font-medium text-navy mb-1.5">{label}</label>
      <div className="relative">
        <input
          type={inputType}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className={`w-full px-4 py-3 rounded-xl text-sm text-navy placeholder-dim outline-none transition-all duration-150 ${
            hasError
              ? "border-2 border-red bg-[rgba(255,71,87,0.04)]"
              : isValid
              ? "border-2 border-teal bg-[rgba(0,201,167,0.04)]"
              : "border border-edge bg-warm focus:border-2 focus:border-navy"
          }`}
        />
        {isPass && (
          <button
            type="button"
            onClick={() => setShow(!show)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-dim hover:text-mid transition-colors"
          >
            {show ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        )}
        {isValid && !isPass && (
          <CheckCircle size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-teal" />
        )}
      </div>
      {error && <p className="text-xs text-red mt-1.5 font-medium">{error}</p>}
      {helper && !error && <p className="text-xs text-dim mt-1.5">{helper}</p>}
    </div>
  )
}

export default function Auth({ mode, navigate, onLogin }: AuthProps) {
  const isLogin = mode === "login"
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  // E3: an instance can close sign-ups once its owner has an account.
  const [registrationEnabled, setRegistrationEnabled] = useState(true)

  useEffect(() => {
    api.getPublicConfig()
      .then(config => setRegistrationEnabled(config.registration_enabled))
      .catch(() => { /* keep the form; the server still rejects sign-ups */ })
  }, [])

  const validate = () => {
    const e: Record<string, string> = {}
    if (!isLogin && name.trim().length < 2) e.name = "Please enter your full name"
    if (!email.includes("@")) e.email = "Please enter a valid email address"
    if (password.length < 8) e.password = "Password must be at least 8 characters"
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!validate()) return
    setLoading(true)
    try {
      if (!isLogin) await api.register({ email, password, full_name: name })
      const result = await api.login({ email, password })
      onLogin(result.access_token)
    } catch (error) {
      setErrors({ form: error instanceof Error ? error.message : "Could not sign in" })
    } finally {
      setLoading(false)
    }
  }

  const benefits = [
    "Instant ATS compatibility scoring",
    "Keyword gap analysis vs. any job description",
    "AI-powered bullet point rewrites",
    "One-click ATS-optimized DOCX export",
  ]

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left panel */}
      <div
        className="hidden lg:flex flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: "linear-gradient(135deg, #0F1C33 0%, #1B2A4A 100%)" }}
      >
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/3 -left-20 w-64 h-64 rounded-full opacity-10" style={{ background: "radial-gradient(circle, #00C9A7, transparent)" }} />
          <div className="absolute bottom-1/4 -right-20 w-64 h-64 rounded-full opacity-8" style={{ background: "radial-gradient(circle, #334d80, transparent)" }} />
        </div>
        <div className="relative flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
            <Zap size={16} className="text-teal" fill="#00C9A7" />
          </div>
          <span className="font-display font-bold text-white text-[15px]">ResumeATS <span className="text-teal">Pro</span></span>
        </div>

        <div className="relative">
          <h2 className="font-display font-bold text-3xl text-white leading-tight mb-4">
            {isLogin ? "Welcome back." : "Your career deserves more than a keyword miss."}
          </h2>
          <p className="text-white/50 text-sm leading-relaxed mb-8">
            {isLogin
              ? "Sign in to access your resume analysis dashboard and continue optimizing for your dream role."
              : "Create an account to score your resume against a real job description and review every suggested change before it is applied."}
          </p>
          <div className="space-y-3">
            {benefits.map((b, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-teal/15 flex items-center justify-center shrink-0">
                  <CheckCircle size={12} className="text-teal" />
                </div>
                <p className="text-white/60 text-sm">{b}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative rounded-2xl p-5" style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)" }}>
          <p className="text-white/70 text-sm leading-relaxed mb-3">
            AI rewriting is off until you enable it. When it runs, you see exactly what would be sent — flagged bullets, the target job title, and skill names — and nothing changes without your approval.
          </p>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-teal/20 flex items-center justify-center">
              <CheckCircle size={14} className="text-teal" />
            </div>
            <div>
              <p className="text-white text-sm font-semibold">Private by default</p>
              <p className="text-white/40 text-xs">Your resume stays yours</p>
            </div>
          </div>
        </div>
      </div>

      {/* Right panel */}
      <div className="flex flex-col justify-center px-6 py-12 bg-warm">
        <div className="max-w-sm mx-auto w-full">
          <button
            onClick={() => navigate("landing")}
            className="flex items-center gap-1.5 text-mid hover:text-navy text-sm mb-8 transition-colors"
          >
            <ArrowLeft size={14} />
            Back to home
          </button>

          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-7 h-7 rounded-lg bg-navy flex items-center justify-center">
              <Zap size={14} className="text-teal" fill="#00C9A7" />
            </div>
            <span className="font-display font-bold text-navy text-sm">ResumeATS <span className="text-teal">Pro</span></span>
          </div>

          <h1 className="font-display font-bold text-2xl text-navy mb-1.5">
            {isLogin ? "Sign in to your account" : "Create your free account"}
          </h1>
          <p className="text-mid text-sm mb-8">
            {isLogin && !registrationEnabled ? (
              "Sign-ups are closed on this instance."
            ) : (
              <>
                {isLogin ? "Don't have an account? " : "Already have an account? "}
                <button
                  onClick={() => navigate(isLogin ? "register" : "login")}
                  className="text-teal font-medium hover:underline"
                >
                  {isLogin ? "Sign up free" : "Sign in"}
                </button>
              </>
            )}
          </p>

          {!isLogin && !registrationEnabled ? (
            <div className="rounded-xl border border-edge bg-surface p-5">
              <p className="text-sm font-semibold text-navy mb-1">Sign-ups are closed on this instance.</p>
              <p className="text-sm text-mid leading-relaxed">
                Ask the person running this instance to create your account, or sign in if you
                already have one.
              </p>
              <button
                onClick={() => navigate("login")}
                className="mt-4 w-full py-3 bg-navy text-white font-semibold rounded-xl text-sm hover:bg-navy-light transition-all"
              >
                Go to sign in
              </button>
            </div>
          ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <InputField
                label="Full Name"
                value={name}
                onChange={setName}
                placeholder="Alex Kim"
                error={errors.name}
              />
            )}
            <InputField
              label="Email Address"
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="you@company.com"
              error={errors.email}
            />
            <InputField
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder={isLogin ? "Your password" : "Min. 8 characters"}
              error={errors.password}
              helper={!isLogin ? "Use a mix of letters, numbers, and symbols" : undefined}
            />

            {isLogin && (
              <div className="text-right">
                <button type="button" className="text-sm text-teal font-medium hover:underline">
                  Forgot password?
                </button>
              </div>
            )}

            {errors.form && <p className="text-sm text-red font-medium">{errors.form}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3.5 bg-navy text-white font-semibold rounded-xl text-sm hover:bg-navy-light transition-all duration-150 disabled:opacity-60 mt-2 group"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  {isLogin ? "Sign In" : "Create Account"}
                  <ArrowRight size={15} className="group-hover:translate-x-0.5 transition-transform" />
                </>
              )}
            </button>
          </form>
          )}

          <div className="mt-8 pt-6 border-t border-edge">
            <p className="text-center text-xs text-dim leading-relaxed">
              By {isLogin ? "signing in" : "creating an account"}, you agree to our{" "}
              <button className="text-mid hover:text-navy underline">Terms of Service</button>{" "}
              and{" "}
              <button className="text-mid hover:text-navy underline">Privacy Policy</button>.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
