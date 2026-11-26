import type { TokenResponse } from '../domain/types'

const rawBase = import.meta.env.VITE_API_BASE_URL as string | undefined
const API_BASE = rawBase ? rawBase.replace(/\/+$/, '') : '/api/v1'

const PROFILE_KEY = 'clubsphere_profile'

/**
 * The access token intentionally lives only in memory. The long-lived refresh
 * token is an HttpOnly cookie set by the API and is never readable by JS.
 */
let accessToken: string | null = null

/** Broadcast on `window` when the session can no longer be refreshed. */
export const AUTH_EXPIRED_EVENT = 'clubsphere:auth-expired'

export class ApiError extends Error {
  readonly status: number
  readonly retryAfterSeconds?: number

  constructor(status: number, message: string, retryAfterSeconds?: number) {
    super(message)
    this.status = status
    this.retryAfterSeconds = retryAfterSeconds
    this.name = 'ApiError'
  }
}

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function saveTokens(tokens: TokenResponse): void {
  accessToken = tokens.access_token
}

export function clearSession(): void {
  accessToken = null
  localStorage.removeItem(PROFILE_KEY)
}

export function readStoredProfile<T>(): T | null {
  const raw = localStorage.getItem(PROFILE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function writeStoredProfile(profile: unknown): void {
  // This contains only display profile data (name/email/role), never tokens.
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile))
}

export function parseRetryAfterSeconds(headerValue: string | null): number | undefined {
  if (!headerValue) return undefined
  const trimmed = headerValue.trim()
  if (!trimmed) return undefined

  const seconds = Number(trimmed)
  if (Number.isFinite(seconds) && seconds > 0) {
    return Math.ceil(seconds)
  }

  const parsedDate = Date.parse(trimmed)
  if (!Number.isNaN(parsedDate)) {
    const diffSeconds = Math.ceil((parsedDate - Date.now()) / 1000)
    return diffSeconds > 0 ? diffSeconds : undefined
  }

  return undefined
}

export function formatRetryAfterMessage(seconds?: number): string {
  if (seconds !== undefined && seconds > 0) {
    const unit = seconds === 1 ? 'second' : 'seconds'
    return `Too many attempts. Please wait ${seconds} ${unit} before trying again.`
  }
  return 'Too many attempts. Please wait a minute before trying again.'
}

async function readErrorMessage(res: Response, retryAfterSeconds?: number): Promise<string> {
  try {
    const data: unknown = await res.json()
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as { detail: unknown }).detail
      if (typeof detail === 'string') {
        if (res.status === 429 && retryAfterSeconds !== undefined && !/\d+\s*second/i.test(detail)) {
          return `${detail.replace(/\.$/, '')}. Please wait ${retryAfterSeconds} ${retryAfterSeconds === 1 ? 'second' : 'seconds'} before trying again.`
        }
        return detail
      }
      if (Array.isArray(detail)) {
        return detail
          .map((d) => {
            if (d && typeof d === 'object' && 'msg' in d) return String((d as { msg: unknown }).msg)
            return JSON.stringify(d)
          })
          .join(' | ')
      }
    }
  } catch {
    // Response was not JSON
  }
  if (res.status === 429) {
    return formatRetryAfterMessage(retryAfterSeconds)
  }
  return `Request failed with status ${res.status}`
}

let refreshPromise: Promise<TokenResponse | null> | null = null

async function performRefresh(): Promise<TokenResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
    if (res.status === 409) {
      // Another tab rotated the cookie in the middle of this request. The
      // browser cookie jar should now hold the new token, so retry once.
      const retry = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
      })
      if (!retry.ok) return null
      const data: TokenResponse = await retry.json()
      accessToken = data.access_token
      return data
    }
    if (!res.ok) return null

    const data: TokenResponse = await res.json()
    accessToken = data.access_token
    return data
  } catch {
    return null
  }
}

/** Exchange the HttpOnly refresh cookie for a fresh in-memory access token. */
export async function refreshSession(): Promise<TokenResponse | null> {
  if (refreshPromise) return refreshPromise
  refreshPromise = performRefresh().finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

const NO_REFRESH_PATHS = new Set(['/auth/login', '/auth/register', '/auth/refresh'])

export async function request<T>(path: string, init: RequestInit = {}, allowRefresh = true): Promise<T> {
  const headers = new Headers(init.headers)
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData
  if (init.body && !isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  })

  if (res.status === 401 && allowRefresh && !NO_REFRESH_PATHS.has(path)) {
    const refreshed = await refreshSession()
    if (refreshed) {
      return request<T>(path, init, false)
    }
    clearSession()
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    throw new ApiError(401, 'Your session has expired. Please sign in again.')
  }

  if (!res.ok) {
    const retryAfterSeconds = parseRetryAfterSeconds(res.headers.get('Retry-After'))
    throw new ApiError(res.status, await readErrorMessage(res, retryAfterSeconds), retryAfterSeconds)
  }

  if (res.status === 204) {
    return undefined as T
  }

  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', body: formData }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

/** Best-effort server-side revocation; local session is cleared regardless. */
export async function revokeSession(): Promise<void> {
  try {
    await api.post<{ message: string }>('/auth/logout')
  } catch {
    // Ignore: the token may already be invalid.
  }
}
