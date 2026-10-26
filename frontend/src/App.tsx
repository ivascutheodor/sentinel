import { useCallback, useEffect, useState } from 'react'
import { Login } from '@/components/auth/login'
import { DashboardShell } from '@/components/dashboard/dashboard-shell'
import type { Section } from '@/components/dashboard/sidebar'

const sections: Partial<Record<string, Section>> = {
  '/dashboard': 'dashboard',
  '/cameras': 'cameras',
  '/events': 'events',
  '/settings': 'settings',
}
const motionPreferenceKey = 'sentinel.reduce-animations'

export default function App() {
  const [path, setPath] = useState(() => window.location.pathname)
  const [reduceAnimations, setReduceAnimations] = useState(() => {
    try { return localStorage.getItem(motionPreferenceKey) === 'true' }
    catch { return false }
  })

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.reduceAnimations = String(reduceAnimations)
  }, [reduceAnimations])

  const navigate = useCallback((nextPath: string, replace = false) => {
    if (window.location.pathname !== nextPath) {
      if (replace) window.history.replaceState(null, '', nextPath)
      else window.history.pushState(null, '', nextPath)
    }
    setPath(nextPath)
  }, [])
  const requireAuth = useCallback(() => navigate('/login', true), [navigate])
  const onNavigate = useCallback((section: Section) => navigate(`/${section}`), [navigate])
  const onReduceAnimationsChange = useCallback((value: boolean) => {
    setReduceAnimations(value)
    try {
      if (value) localStorage.setItem(motionPreferenceKey, 'true')
      else localStorage.removeItem(motionPreferenceKey)
    } catch { /* Keep the preference for this tab if browser storage is unavailable. */ }
  }, [])
  const section = sections[path.replace(/\/$/, '')]

  return section
    ? <DashboardShell section={section} onNavigate={onNavigate} onRequireAuth={requireAuth} reduceAnimations={reduceAnimations} onReduceAnimationsChange={onReduceAnimationsChange} />
    : <Login onSuccess={() => navigate('/dashboard', true)} />
}
