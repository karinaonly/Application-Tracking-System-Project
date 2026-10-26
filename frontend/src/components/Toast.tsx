import { CheckCircle, XCircle, Info, X } from "lucide-react"
import type { ToastMsg } from "../types"

const config = {
  success: { icon: CheckCircle, bg: "#ECFDF5", border: "#00C9A7", text: "#065F46", iconColor: "#00C9A7" },
  error:   { icon: XCircle,    bg: "#FFF1F2", border: "#FF4757", text: "#9F1239", iconColor: "#FF4757" },
  info:    { icon: Info,       bg: "#EFF6FF", border: "#3B82F6", text: "#1E40AF", iconColor: "#3B82F6" },
}

export default function Toast({ toast, onDismiss }: { toast: ToastMsg; onDismiss?: (id: string) => void }) {
  const c = config[toast.type]
  const Icon = c.icon
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border max-w-sm animate-fade-in"
      style={{ background: c.bg, borderColor: c.border }}
    >
      <Icon size={18} style={{ color: c.iconColor, flexShrink: 0 }} />
      <p className="text-sm font-medium flex-1" style={{ color: c.text }}>{toast.text}</p>
      {onDismiss && (
        <button onClick={() => onDismiss(toast.id)} className="opacity-50 hover:opacity-100 transition-opacity">
          <X size={14} style={{ color: c.text }} />
        </button>
      )}
    </div>
  )
}
