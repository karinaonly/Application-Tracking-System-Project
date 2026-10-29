import { useEffect, useState } from "react"
import { User, Key, Bell, Moon, Save, Zap, ShieldCheck } from "lucide-react"
import type { PageProps } from "../types"
import * as api from "../api"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface rounded-2xl border border-edge overflow-hidden">
      <div className="px-6 py-4 border-b border-edge">
        <h2 className="font-display font-semibold text-base text-navy">{title}</h2>
      </div>
      <div className="p-6">{children}</div>
    </div>
  )
}

function Field({ label, note, children }: { label: string; note?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-navy mb-1.5">{label}</label>
      {children}
      {note && <p className="text-xs text-dim mt-1.5">{note}</p>}
    </div>
  )
}

export default function Settings({ addToast }: PageProps) {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [currentPw, setCurrentPw] = useState("")
  const [newPw, setNewPw] = useState("")
  const [aiStatus, setAIStatus] = useState<api.AIStatus | null>(null)
  // E4: browser-local opt-out; the server enforces its own switch on top.
  const [aiEnabled, setAiEnabled] = useState(api.getAiRewritingPreference)
  const [darkMode, setDarkMode] = useState(false)
  const [emailNotifs, setEmailNotifs] = useState(true)
  const [savingProfile, setSavingProfile] = useState(false)
  const [savingPw, setSavingPw] = useState(false)

  useEffect(() => {
    Promise.all([api.getMe(), api.getAIStatus()])
      .then(([user, status]) => { setName(user.full_name); setEmail(user.email); setAIStatus(status) })
      .catch(error => addToast("error", error.message))
  }, [addToast])

  const inputCls = "w-full px-4 py-3 rounded-xl border border-edge bg-warm text-sm text-navy placeholder-dim outline-none focus:border-2 focus:border-navy transition-all"
  const disabledCls = "w-full px-4 py-3 rounded-xl border border-edge bg-off text-sm text-mid cursor-not-allowed"

  const saveProfile = async () => {
    if (!name.trim()) { addToast("error", "Name cannot be empty"); return }
    setSavingProfile(true)
    try {
      const updated = await api.updateMe({ full_name: name.trim() })
      setName(updated.full_name)
      addToast("success", "Profile updated")
    } catch (error) {
      addToast("error", error instanceof Error ? error.message : "Could not update profile")
    } finally {
      setSavingProfile(false)
    }
  }

  const savePw = async () => {
    if (!currentPw || !newPw) { addToast("error", "Please fill in both password fields"); return }
    if (newPw.length < 8) { addToast("error", "New password must be at least 8 characters"); return }
    setSavingPw(true)
    try {
      await api.changePassword({ current_password: currentPw, new_password: newPw })
      setCurrentPw("")
      setNewPw("")
      addToast("success", "Password updated")
    } catch (error) {
      addToast("error", error instanceof Error ? error.message : "Could not update password")
    } finally {
      setSavingPw(false)
    }
  }

  const serverAiEnabled = aiStatus?.rewriting_enabled !== false
  const toggleAi = () => {
    const next = !aiEnabled
    setAiEnabled(next)
    api.setAiRewritingPreference(next)
    addToast("info", next
      ? "AI rewriting on — new analyses may send flagged bullets to your AI provider."
      : "AI rewriting off — new analyses will stay on this machine.")
  }

  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase() ?? "")
    .join("") || "?"

  return (
    <div className="min-h-screen bg-warm">
      <div className="max-w-3xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="font-display font-bold text-2xl text-navy mb-1">Settings</h1>
          <p className="text-mid text-sm">Manage your profile, API integrations, and preferences.</p>
        </div>

        <div className="space-y-5">
          {/* Profile */}
          <Section title="Profile Information">
            <div className="flex items-center gap-5 mb-6 pb-6 border-b border-edge">
              <div className="w-16 h-16 rounded-2xl bg-navy flex items-center justify-center shrink-0">
                <span className="text-white text-xl font-bold font-display">{initials}</span>
              </div>
              <div>
                <p className="font-semibold text-navy">{name}</p>
                <p className="text-sm text-mid">{email}</p>
                <div className="flex items-center gap-1.5 mt-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-teal" />
                  <span className="text-xs text-teal font-medium">Local instance · your data stays on this machine</span>
                </div>
              </div>
            </div>
            <div className="space-y-4">
              <Field label="Full Name">
                <input value={name} onChange={e => setName(e.target.value)} className={inputCls} />
              </Field>
              <Field label="Email Address" note="Contact support to change your email address.">
                <input value={email} disabled className={disabledCls} />
              </Field>
              <div className="flex justify-end pt-2">
                <button
                  onClick={saveProfile}
                  disabled={savingProfile}
                  className="flex items-center gap-2 px-5 py-2.5 bg-navy text-white text-sm font-semibold rounded-xl hover:bg-navy-light transition-all disabled:opacity-60"
                >
                  {savingProfile ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Save size={14} />}
                  Save Changes
                </button>
              </div>
            </div>
          </Section>

          {/* Password */}
          <Section title="Change Password">
            <div className="space-y-4">
              <Field label="Current Password">
                <input type="password" value={currentPw} onChange={e => setCurrentPw(e.target.value)} placeholder="Your current password" className={inputCls} />
              </Field>
              <Field label="New Password" note="Minimum 8 characters. Use a mix of letters, numbers, and symbols.">
                <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} placeholder="At least 8 characters" className={inputCls} />
              </Field>
              <div className="flex justify-end pt-2">
                <button
                  onClick={savePw}
                  disabled={savingPw}
                  className="flex items-center gap-2 px-5 py-2.5 bg-navy text-white text-sm font-semibold rounded-xl hover:bg-navy-light transition-all disabled:opacity-60"
                >
                  {savingPw ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Key size={14} />}
                  Update Password
                </button>
              </div>
            </div>
          </Section>

          {/* API Config */}
          <Section title="API Configuration">
            <div className="flex items-start gap-3 p-4 rounded-xl mb-5" style={{ background: "rgba(27,42,74,0.04)", border: "1px solid rgba(27,42,74,0.08)" }}>
              <Zap size={16} className="text-teal mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-navy mb-0.5">AI API Configuration</p>
                <p className="text-xs text-mid leading-relaxed">
                  The backend reads the configured AI provider key from its private environment configuration. It is never sent to or stored in the browser.
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium ${aiStatus?.configured ? "bg-teal/10 text-teal" : "bg-off text-mid"}`}>
                  <div className={`w-2 h-2 rounded-full ${aiStatus?.configured ? "bg-teal" : "bg-dim"}`} />
                  {aiStatus
                    ? aiStatus.configured
                      ? `Connected — ${aiStatus.model} rewrites active`
                      : aiStatus.reason === "invalid_format"
                      ? "Provider key rejected — check its format in backend/.env"
                      : aiStatus.reason === "quota_exhausted"
                      ? "AI quota exhausted — using rule-based fallback"
                      : aiStatus.reason === "model_unavailable"
                      ? "Configured model unavailable — update AI_MODEL"
                      : "Not configured — using rule-based fallback"
                    : "Checking backend configuration…"}
                </div>
              </div>
              <p className="text-xs text-dim">Set the provider key in `backend/.env`, then restart the backend. The key is not exposed through this page.</p>
            </div>
          </Section>

          {/* E4: privacy notice + AI opt-out */}
          <Section title="Privacy & Data">
            <div className="flex items-start gap-3 p-4 rounded-xl mb-5" style={{ background: "rgba(27,42,74,0.04)", border: "1px solid rgba(27,42,74,0.08)" }}>
              <ShieldCheck size={16} className="text-teal mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-navy mb-0.5">What leaves this machine</p>
                <p className="text-xs text-mid leading-relaxed">
                  ATS, keyword, bullet, and grammar checks always run locally. Only AI rewriting
                  sends data out: up to 8 flagged bullet lines, the target job title, and skill
                  names go to your configured provider. Your contact details and the rest of the
                  resume are not sent.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-navy">AI bullet rewriting</p>
                <p className="text-xs text-dim">
                  {serverAiEnabled
                    ? "Turn this off to keep every analysis on this machine. Rule-based suggestions still appear."
                    : "Disabled on this instance — no resume text is sent to any AI provider."}
                </p>
              </div>
              <button
                onClick={toggleAi}
                disabled={!serverAiEnabled}
                aria-pressed={aiEnabled && serverAiEnabled}
                className={`relative w-11 h-6 rounded-full transition-all duration-200 shrink-0 ${
                  aiEnabled && serverAiEnabled ? "bg-teal" : "bg-edge"
                } ${serverAiEnabled ? "" : "opacity-50 cursor-not-allowed"}`}
              >
                <div className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-200 ${
                  aiEnabled && serverAiEnabled ? "left-6" : "left-1"
                }`} />
              </button>
            </div>
            <p className="text-xs text-dim mt-4">
              This preference is stored in this browser and applies to new analyses. You can also
              switch it off right before an analysis on the Upload page.
            </p>
          </Section>

          {/* Preferences */}
          <Section title="Preferences">
            <div className="space-y-5">
              {[
                {
                  icon: Moon,
                  title: "Dark Mode",
                  desc: "Use a dark color scheme across the application. (Coming soon)",
                  state: darkMode,
                  toggle: () => { setDarkMode(!darkMode); addToast("info", "Dark mode coming soon — stay tuned!") },
                },
                {
                  icon: Bell,
                  title: "Email Notifications",
                  desc: "Receive email summaries when new analysis features are released.",
                  state: emailNotifs,
                  toggle: () => { setEmailNotifs(!emailNotifs); addToast("success", emailNotifs ? "Email notifications disabled" : "Email notifications enabled") },
                },
              ].map((p, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-off flex items-center justify-center">
                      <p.icon size={16} className="text-mid" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-navy">{p.title}</p>
                      <p className="text-xs text-dim">{p.desc}</p>
                    </div>
                  </div>
                  <button
                    onClick={p.toggle}
                    className={`relative w-11 h-6 rounded-full transition-all duration-200 ${p.state ? "bg-teal" : "bg-edge"}`}
                  >
                    <div className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-200 ${p.state ? "left-6" : "left-1"}`} />
                  </button>
                </div>
              ))}
            </div>
          </Section>

          {/* Danger zone */}
          <div className="rounded-2xl border border-red/20 overflow-hidden">
            <div className="px-6 py-4 border-b border-red/10 bg-red/3">
              <h2 className="font-display font-semibold text-base text-red">Danger Zone</h2>
            </div>
            <div className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-navy">Delete Account</p>
                  <p className="text-xs text-dim mt-0.5">Permanently remove your account and all associated data. This action cannot be undone.</p>
                </div>
                <button
                  onClick={() => addToast("error", "Please contact support to delete your account.")}
                  className="px-4 py-2 text-sm font-medium text-red border border-red/20 rounded-xl hover:bg-red/8 transition-colors shrink-0 ml-4"
                >
                  Delete Account
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
