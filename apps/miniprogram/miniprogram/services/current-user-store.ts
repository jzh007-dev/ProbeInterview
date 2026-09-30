import type {ProfileOverview} from "./profile-overview"

export const CURRENT_USER_CACHE_SCHEMA_VERSION = 2
export const CURRENT_USER_CACHE_KEY = "probeinterview:current-user:v2"

export interface DefaultTargetProfileSummary {
  targetRole: string
  relevantExperienceMonths: number
}

export interface CurrentUserSnapshot {
  schemaVersion: typeof CURRENT_USER_CACHE_SCHEMA_VERSION
  userId: string
  nickname: string
  avatarUrl: string | null
  avatarUrlExpiresAt: string | null
  defaultTargetProfile: DefaultTargetProfileSummary | null
}

export interface CurrentUserDisplayResource {
  id: string
  nickname: string
  avatar_url: string | null
  avatar_url_expires_at: string | null
  default_target_profile: {
    target_role: string
    relevant_experience_months: number
  } | null
}

let memorySnapshot: CurrentUserSnapshot | null = null

export function readCurrentUserSnapshot(
  now: Date = new Date(),
): CurrentUserSnapshot | null {
  if (memorySnapshot !== null) {
    return withResolvedAvatar(memorySnapshot, now)
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

  memorySnapshot = storedValue
  return withResolvedAvatar(memorySnapshot, now)
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

export function currentUserSnapshotFromResource(
  resource: CurrentUserDisplayResource,
): CurrentUserSnapshot {
  const userId = resource.id.trim()
  const nickname = resource.nickname.trim()
  if (!userId || !nickname) {
    throw new Error("Current user resource is missing display fields.")
  }

  const avatarUrl = resource.avatar_url?.trim() ?? ""
  const avatarUrlExpiresAt = resource.avatar_url_expires_at?.trim() ?? ""
  if (avatarUrl && !avatarUrlExpiresAt) {
    throw new Error("A signed avatar URL must carry its expiry.")
  }
  if (!avatarUrl && avatarUrlExpiresAt) {
    throw new Error("An avatar expiry requires a signed avatar URL.")
  }

  const profile = resource.default_target_profile
  const targetRole = profile?.target_role.trim() ?? ""
  if (profile !== null && !targetRole) {
    throw new Error("A default target profile must carry a target role.")
  }

  return {
    schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
    userId,
    nickname,
    avatarUrl: avatarUrl || null,
    avatarUrlExpiresAt: avatarUrlExpiresAt || null,
    defaultTargetProfile:
      profile === null
        ? null
        : {
            targetRole,
            relevantExperienceMonths: profile.relevant_experience_months,
          },
  }
}

export function currentUserSnapshotFromOverview(
  overview: ProfileOverview,
): CurrentUserSnapshot {
  return currentUserSnapshotFromResource(overview)
}

export function clearCurrentUserSnapshot(): void {
  memorySnapshot = null
  removeStoredSnapshot()
}

export function resetCurrentUserMemoryForTests(): void {
  memorySnapshot = null
}

function withResolvedAvatar(
  snapshot: CurrentUserSnapshot,
  now: Date,
): CurrentUserSnapshot {
  const resolved = {...snapshot}
  if (resolved.avatarUrlExpiresAt === null) {
    return resolved
  }

  const expiresAt = Date.parse(resolved.avatarUrlExpiresAt)
  if (!Number.isNaN(expiresAt) && expiresAt <= now.getTime()) {
    resolved.avatarUrl = null
    resolved.avatarUrlExpiresAt = null
  }
  return resolved
}

function isCurrentUserSnapshot(value: unknown): value is CurrentUserSnapshot {
  if (typeof value !== "object" || value === null) {
    return false
  }

  const candidate = value as Record<string, unknown>
  if (
    candidate.schemaVersion !== CURRENT_USER_CACHE_SCHEMA_VERSION ||
    !isNonEmptyString(candidate.userId) ||
    !isNonEmptyString(candidate.nickname) ||
    !isNullableString(candidate.avatarUrl) ||
    !isNullableString(candidate.avatarUrlExpiresAt)
  ) {
    return false
  }

  const avatarUrl = candidate.avatarUrl?.trim() || null
  const avatarUrlExpiresAt = candidate.avatarUrlExpiresAt?.trim() || null
  if ((avatarUrl === null) !== (avatarUrlExpiresAt === null)) {
    return false
  }

  const profile = candidate.defaultTargetProfile
  if (profile === null) {
    return true
  }
  if (typeof profile !== "object") {
    return false
  }
  const profileCandidate = profile as Record<string, unknown>
  return (
    isNonEmptyString(profileCandidate.targetRole) &&
    typeof profileCandidate.relevantExperienceMonths === "number" &&
    Number.isInteger(profileCandidate.relevantExperienceMonths) &&
    profileCandidate.relevantExperienceMonths >= 0
  )
}

function normalizeSnapshot(snapshot: CurrentUserSnapshot): CurrentUserSnapshot {
  const avatarUrl = snapshot.avatarUrl?.trim() ?? ""
  const avatarUrlExpiresAt = snapshot.avatarUrlExpiresAt?.trim() ?? ""
  const targetRole = snapshot.defaultTargetProfile?.targetRole.trim() ?? ""
  return {
    schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
    userId: snapshot.userId.trim(),
    nickname: snapshot.nickname.trim(),
    avatarUrl: avatarUrl || null,
    avatarUrlExpiresAt: avatarUrlExpiresAt || null,
    defaultTargetProfile:
      snapshot.defaultTargetProfile === null
        ? null
        : {
            targetRole,
            relevantExperienceMonths:
              snapshot.defaultTargetProfile.relevantExperienceMonths,
          },
  }
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string"
}

function removeStoredSnapshot(): void {
  try {
    wx.removeStorageSync(CURRENT_USER_CACHE_KEY)
  } catch {
    // Invalid or obsolete display state is ignored even if removal fails.
  }
}
