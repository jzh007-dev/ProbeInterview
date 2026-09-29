import type {ProfileOverview} from "./profile-overview"

export const CURRENT_USER_CACHE_SCHEMA_VERSION = 1
export const CURRENT_USER_CACHE_KEY = "probeinterview:current-user:v1"

export interface CurrentUserSnapshot {
  schemaVersion: typeof CURRENT_USER_CACHE_SCHEMA_VERSION
  userId: string
  nickname: string
  avatarUrl?: string
}

let memorySnapshot: CurrentUserSnapshot | null = null

export function readCurrentUserSnapshot(): CurrentUserSnapshot | null {
  if (memorySnapshot !== null) {
    return {...memorySnapshot}
  }

  let storedValue: unknown
  try {
    storedValue = wx.getStorageSync(CURRENT_USER_CACHE_KEY)
  } catch {
    return null
  }

  if (storedValue === undefined || storedValue === null || storedValue === "") {
    return null
  }
  if (!isCurrentUserSnapshot(storedValue)) {
    removeStoredSnapshot()
    return null
  }

  memorySnapshot = normalizeSnapshot(storedValue)
  return {...memorySnapshot}
}

export function writeCurrentUserSnapshot(
  snapshot: CurrentUserSnapshot,
): CurrentUserSnapshot {
  if (!isCurrentUserSnapshot(snapshot)) {
    throw new Error("Invalid current user snapshot.")
  }

  memorySnapshot = normalizeSnapshot(snapshot)
  try {
    wx.setStorageSync(CURRENT_USER_CACHE_KEY, memorySnapshot)
  } catch {
    // Display state remains usable in memory when device storage is unavailable.
  }
  return {...memorySnapshot}
}

export function currentUserSnapshotFromOverview(
  overview: ProfileOverview,
): CurrentUserSnapshot {
  const userId = overview.id.trim()
  const nickname = overview.nickname.trim()
  if (!userId || !nickname) {
    throw new Error("Profile overview is missing current user display fields.")
  }

  const avatarUrl = overview.avatar_url.trim()
  return {
    schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
    userId,
    nickname,
    ...(avatarUrl ? {avatarUrl} : {}),
  }
}

export function clearCurrentUserSnapshot(): void {
  memorySnapshot = null
  removeStoredSnapshot()
}

export function resetCurrentUserMemoryForTests(): void {
  memorySnapshot = null
}

function isCurrentUserSnapshot(value: unknown): value is CurrentUserSnapshot {
  if (typeof value !== "object" || value === null) {
    return false
  }

  const candidate = value as Record<string, unknown>
  return (
    candidate.schemaVersion === CURRENT_USER_CACHE_SCHEMA_VERSION &&
    isNonEmptyString(candidate.userId) &&
    isNonEmptyString(candidate.nickname) &&
    (candidate.avatarUrl === undefined ||
      typeof candidate.avatarUrl === "string")
  )
}

function normalizeSnapshot(snapshot: CurrentUserSnapshot): CurrentUserSnapshot {
  const avatarUrl = snapshot.avatarUrl?.trim()
  return {
    schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
    userId: snapshot.userId.trim(),
    nickname: snapshot.nickname.trim(),
    ...(avatarUrl ? {avatarUrl} : {}),
  }
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

function removeStoredSnapshot(): void {
  try {
    wx.removeStorageSync(CURRENT_USER_CACHE_KEY)
  } catch {
    // Invalid or obsolete display state is ignored even if removal fails.
  }
}
