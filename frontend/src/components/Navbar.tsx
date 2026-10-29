import { useState } from "react"
import { LayoutDashboard, FileText, Briefcase, Settings, ChevronDown, LogOut, User, Zap } from "lucide-react"
import type { Page } from "../types"

interface NavbarProps {
  currentPage: Page
  navigate: (p: Page) => void
  onLogout: () => void
}

const navItems = [
  { id: "dashboard" as Page, label: "Dashboard", icon: LayoutDashboard },
  { id: "upload" as Page,    label: "My Resumes", icon: FileText },
  { id: "jobs" as Page,      label: "Job Descriptions", icon: Briefcase },
  { id: "settings" as Page,  label: "Settings", icon: Settings },
]

export default function Navbar({ currentPage, navigate, onLogout }: NavbarProps) {
  const [open, setOpen] = useState(false)

  return (
    <nav className="sticky top-0 z-40 bg-surface border-b border-edge" style={{ boxShadow: "0 1px 3px rgba(27,42,74,0.06)" }}>
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-6">
        <button onClick={() => navigate("dashboard")} className="flex items-center gap-2.5 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-navy flex items-center justify-center">
            <Zap size={16} className="text-teal" fill="#00C9A7" />
          </div>
          <span className="font-display font-bold text-navy text-[15px] tracking-tight">
            Land<span className="text-teal">It</span>
          </span>
        </button>

        <div className="flex items-center gap-0.5">
          {navItems.map(item => {
            const active = currentPage === item.id
            return (
              <button
                key={item.id}
                onClick={() => navigate(item.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                  active
                    ? "bg-[rgba(0,201,167,0.1)] text-teal"
                    : "text-mid hover:text-navy hover:bg-off"
                }`}
              >
                <item.icon size={15} />
                {item.label}
              </button>
            )
          })}
        </div>

        <div className="relative shrink-0">
          <button
            onClick={() => setOpen(!open)}
            className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg hover:bg-off transition-all"
          >
            <div className="w-7 h-7 rounded-full bg-navy flex items-center justify-center">
              <span className="text-white text-[11px] font-bold font-display">AK</span>
            </div>
            <div className="text-left">
              <p className="text-sm font-medium text-navy leading-none">Alex Kim</p>
              <p className="text-[11px] text-mid leading-none mt-0.5">alex@techcorp.io</p>
            </div>
            <ChevronDown size={14} className={`text-mid transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
          </button>

          {open && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
              <div className="absolute right-0 top-full mt-1.5 w-52 bg-surface rounded-xl border border-edge py-1.5 z-50" style={{ boxShadow: "0 8px 24px rgba(27,42,74,0.12)" }}>
                <div className="px-4 py-2 border-b border-edge mb-1">
                  <p className="text-xs font-medium text-navy">alex@techcorp.io</p>
                  <p className="text-[11px] text-mid">Account</p>
                </div>
                <button
                  onClick={() => { navigate("settings"); setOpen(false) }}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-navy hover:bg-off transition-colors"
                >
                  <User size={14} className="text-mid" />
                  Profile & Settings
                </button>
                <div className="border-t border-edge my-1" />
                <button
                  onClick={onLogout}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-red hover:bg-[rgba(255,71,87,0.06)] transition-colors"
                >
                  <LogOut size={14} />
                  Sign Out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
