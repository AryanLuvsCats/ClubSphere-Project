import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

type ToastTone = 'success' | 'error'
interface ToastItem { id: number; tone: ToastTone; message: string }
interface ToastApi {
  success: (message: string) => void
  error: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(0)
  const timers = useRef(new Map<number, number>())

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id)
    if (timer) window.clearTimeout(timer)
    timers.current.delete(id)
    setItems((current) => current.filter((item) => item.id !== id))
  }, [])

  const show = useCallback((tone: ToastTone, message: string) => {
    const id = ++nextId.current
    setItems((current) => [...current, { id, tone, message }])
    timers.current.set(id, window.setTimeout(() => dismiss(id), 4500))
  }, [dismiss])

  useEffect(() => () => {
    timers.current.forEach((timer) => window.clearTimeout(timer))
    timers.current.clear()
  }, [])

  const api = useRef<ToastApi>({
    success: (message) => show('success', message),
    error: (message) => show('error', message),
  })
  api.current.success = (message) => show('success', message)
  api.current.error = (message) => show('error', message)

  return (
    <ToastContext.Provider value={api.current}>
      {children}
      <div className="toast-stack" aria-label="Notifications">
        {items.map((item) => (
          <div key={item.id} className={`toast-message toast-${item.tone}`} role={item.tone === 'error' ? 'alert' : 'status'}>
            <span>{item.message}</span>
            <button type="button" onClick={() => dismiss(item.id)} aria-label="Dismiss notification">×</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const toast = useContext(ToastContext)
  if (!toast) throw new Error('useToast must be used inside a <ToastProvider>')
  return toast
}
