export const AUTH_SESSION_CACHE_SCHEMA_VERSION = 1
export const AUTH_SESSION_CACHE_KEY = "probeinterview:auth-session:v1"

export interface AuthSessionSnapshot {
  schemaVersion: typeof AUTH_SESSION_CACHE_SCHEMA_VERSION
  accessToken: string
  expiresAt: string
}

let memorySession: AuthSessionSnapshot | null = null

export function readAuthSession(now: Date = new Date()): AuthSessionSnapshot | null {
  if (memorySession === null) {
    let storedValue: unknown
    try {
      storedValue = wx.getStorageSync(AUTH_SESSION_CACHE_KEY)
    } catch {
      return null
    }

    if (storedValue === undefined || storedValue === null || storedValue === "") {
      return null
    }
    if (!isAuthSessionSnapshot(storedValue)) {
      removeStoredSession()
      return null
    }
    memorySession = storedValue
  }

  const session = memorySession
  if (isAuthSessionExpired(session, now)) {
    memorySession = null
    removeStoredSession()
    return null
  }
  return {...session}
}

export function writeAuthSession(
  session: AuthSessionSnapshot,
): AuthSessionSnapshot {
  const normalized = normalizeSession(session)
  if (normalized === null) {
    throw new Error("Invalid auth session snapshot.")
  }

  memorySession = normalized
  try {
    wx.setStorageSync(AUTH_SESSION_CACHE_KEY, normalized)
  } catch {
    // The in-memory session keeps the app usable when device storage fails.
  }
  return {...normalized}
}

export function clearAuthSession(): void {
  memorySession = null
  removeStoredSession()
}

export function resetAuthSessionMemoryForTests(): void {
  memorySession = null
}

function isAuthSessionExpired(session: AuthSessionSnapshot, now: Date): boolean {
  const expiresAt = Date.parse(session.expiresAt)
  if (Number.isNaN(expiresAt)) {
    return true
  }
  return expiresAt <= now.getTime()
}

function isAuthSessionSnapshot(value: unknown): value is AuthSessionSnapshot {
  if (typeof value !== "object" || value === null) {
    return false
  }

  const candidate = value as Record<string, unknown>
  return (
    candidate.schemaVersion === AUTH_SESSION_CACHE_SCHEMA_VERSION &&
    isNonEmptyString(candidate.accessToken) &&
    isNonEmptyString(candidate.expiresAt) &&
    !Number.isNaN(Date.parse(candidate.expiresAt))
  )
}

function normalizeSession(
  session: AuthSessionSnapshot,
): AuthSessionSnapshot | null {
  if (session.schemaVersion !== AUTH_SESSION_CACHE_SCHEMA_VERSION) {
    return null
  }
  const accessToken = session.accessToken.trim()
  const expiresAt = session.expiresAt.trim()
  if (!accessToken || !expiresAt || Number.isNaN(Date.parse(expiresAt))) {
    return null
  }
  return {
    schemaVersion: AUTH_SESSION_CACHE_SCHEMA_VERSION,
    accessToken,
    expiresAt,
  }
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

function removeStoredSession(): void {
  try {
    wx.removeStorageSync(AUTH_SESSION_CACHE_KEY)
  } catch {
    // A stale session entry is harmless if removal itself fails.
  }
}
