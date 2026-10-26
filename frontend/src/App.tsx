import { useCallback, useEffect, useState } from "react"
import type { Page, ToastMsg } from "./types"
import Navbar from "./components/Navbar"
import Toast from "./components/Toast"
import Landing from "./pages/Landing"
import Auth from "./pages/Auth"
import Dashboard from "./pages/Dashboard"
import UploadPage from "./pages/Upload"
import JobDescriptions from "./pages/JobDescriptions"
import Analysis from "./pages/Analysis"
import Settings from "./pages/Settings"
import * as api from "./api"

const AUTHED: Page[] = ["dashboard", "upload", "jobs", "analysis", "settings"]

export default function App() {
  const [page, setPage] = useState<Page>("landing")
  const [toasts, setToasts] = useState<ToastMsg[]>([])

  useEffect(() => {
    if (!api.getToken()) return
    api.getMe().then(() => navigate("dashboard")).catch(() => api.clearToken())
  }, [])

  // A20: stable identity so consumers' effects don't re-fire every render
  const navigate = useCallback((p: Page) => {
    setPage(p)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }, [])

  const addToast = useCallback((type: ToastMsg["type"], text: string) => {
    const id = Math.random().toString(36).slice(2)
    setToasts(prev => [...prev, { id, type, text }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500)
  }, [])

  const dismissToast = useCallback((id: string) => setToasts(prev => prev.filter(t => t.id !== id)), [])

  const handleLogin = (token: string) => {
    api.setToken(token)
    navigate("dashboard")
    addToast("success", "Welcome back! You're signed in.")
  }
  const handleLogout = () => {
    api.clearToken()
    navigate("landing")
    addToast("info", "You've been signed out.")
  }

  const isAuthed = AUTHED.includes(page)
  const pageProps = { navigate, addToast }

  return (
    <div className="min-h-screen bg-warm font-body">
      {isAuthed && <Navbar currentPage={page} navigate={navigate} onLogout={handleLogout} />}

      {page === "landing"   && <Landing navigate={navigate} />}
      {page === "login"     && <Auth mode="login"    navigate={navigate} onLogin={handleLogin} />}
      {page === "register"  && <Auth mode="register" navigate={navigate} onLogin={handleLogin} />}
      {page === "dashboard" && <Dashboard  {...pageProps} />}
      {page === "upload"    && <UploadPage {...pageProps} />}
      {page === "jobs"      && <JobDescriptions {...pageProps} />}
      {page === "analysis"  && <Analysis   {...pageProps} />}
      {page === "settings"  && <Settings   {...pageProps} />}

      <div className="fixed bottom-5 right-5 flex flex-col gap-2 z-50 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id} className="pointer-events-auto">
            <Toast toast={t} onDismiss={dismissToast} />
          </div>
        ))}
      </div>
    </div>
  )
}
