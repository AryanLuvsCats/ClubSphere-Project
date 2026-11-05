import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AUTH_EXPIRED_EVENT,
  clearSession,
} from '../services/apiClient'
import { authService, type RegisterInput } from '../services/authService'
import { AuthContext, type AuthContextValue } from './AuthContextInstance'
import type { SessionProfile } from '../domain/types'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionProfile | null>(null)
  const [isInitializing, setIsInitializing] = useState(true)

  useEffect(() => {
    let cancelled = false

    // On a full page reload the in-memory access token is gone, but the
    // HttpOnly refresh cookie may still be valid. Bootstrap through the API
    // instead of trusting localStorage.
    void authService
      .restoreSession()
      .then((profile) => {
        if (!cancelled) setUser(profile)
      })
      .finally(() => {
        if (!cancelled) setIsInitializing(false)
      })

    const onExpired = () => {
      clearSession()
      setUser(null)
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    return () => {
      cancelled = true
      window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const profile = await authService.login(email, password)
    setUser(profile)
    setIsInitializing(false)
  }, [])

  const register = useCallback(async (input: RegisterInput) => {
    return authService.register(input)
  }, [])

  const logout = useCallback(async () => {
    await authService.logout()
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isInitializing,
      login,
      register,
      logout,
    }),
    [user, isInitializing, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
