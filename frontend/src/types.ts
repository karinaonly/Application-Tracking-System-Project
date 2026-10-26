export type Page = "landing" | "login" | "register" | "dashboard" | "upload" | "jobs" | "analysis" | "settings"

export interface ToastMsg {
  id: string
  type: "success" | "error" | "info"
  text: string
}

export interface PageProps {
  navigate: (p: Page) => void
  addToast: (type: ToastMsg["type"], text: string) => void
}
