import type {ProfileOverview, TargetProfileOverview} from "../services/profile-overview"

export const TARGET_ROLE_MAX_LENGTH = 200
export const EXPERIENCE_MONTHS_MAX = 600

export function formatExperience(months: number): string {
  if (months < 12) {
    return `${months} 个月`
  }
  const years = Math.floor(months / 12)
  const remainingMonths = months % 12
  if (remainingMonths === 0) {
    return `${years} 年`
  }
  return `${years} 年 ${remainingMonths} 个月`
}

export function avatarInitials(nickname: string): string {
  const normalized = nickname.trim()
  if (!normalized) {
    return "?"
  }
  const words = normalized.split(/\s+/)
  if (words.length > 1) {
    return words
      .slice(0, 2)
      .map((word) => Array.from(word)[0] ?? "")
      .join("")
      .toUpperCase()
  }
  return Array.from(normalized).slice(0, 2).join("").toUpperCase()
}

export function validateTargetRoleInput(value: string): string | null {
  const normalized = value.trim()
  if (!normalized || normalized.length > TARGET_ROLE_MAX_LENGTH) {
    return null
  }
  for (const character of normalized) {
    const codePoint = character.codePointAt(0) ?? 0
    if (codePoint <= 0x1f || (codePoint >= 0x7f && codePoint <= 0x9f)) {
      return null
    }
  }
  return normalized
}

export function parseExperienceMonthsInput(value: string): number | null {
  const normalized = value.trim()
  if (!/^\d+$/.test(normalized)) {
    return null
  }
  const months = Number(normalized)
  if (!Number.isSafeInteger(months) || months > EXPERIENCE_MONTHS_MAX) {
    return null
  }
  return months
}

export function parseProfileOverview(value: unknown): ProfileOverview | null {
  if (typeof value !== "object" || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  if (!isNonEmptyString(record.id) || !isNonEmptyString(record.nickname)) {
    return null
  }

  const avatarUrl = optionalDisplayString(record.avatar_url)
  const avatarUrlExpiresAt = optionalDisplayString(record.avatar_url_expires_at)
  if ((avatarUrl === null) !== (avatarUrlExpiresAt === null)) {
    return null
  }

  const profile = parseTargetProfileSummary(record.default_target_profile)
  if (profile === undefined) {
    return null
  }

  const resume = parseCurrentResume(record.current_resume)
  if (resume === undefined) {
    return null
  }
  if (!Array.isArray(record.recent_scores)) {
    return null
  }

  return {
    id: record.id,
    nickname: record.nickname,
    avatar_url: avatarUrl,
    avatar_url_expires_at: avatarUrlExpiresAt,
    default_target_profile: profile,
    current_resume: resume,
    recent_scores: record.recent_scores,
  }
}

export function parseTargetProfileResource(
  value: unknown,
): TargetProfileOverview | null {
  if (typeof value !== "object" || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  if (
    !isNonEmptyString(record.id) ||
    !isNonEmptyString(record.target_role) ||
    typeof record.relevant_experience_months !== "number" ||
    !Number.isInteger(record.relevant_experience_months) ||
    record.relevant_experience_months < 0
  ) {
    return null
  }
  return {
    id: record.id,
    target_role: record.target_role,
    relevant_experience_months: record.relevant_experience_months,
  }
}

function parseTargetProfileSummary(
  value: unknown,
): TargetProfileOverview | null | undefined {
  if (value === null || value === undefined) {
    return null
  }
  const parsed = parseTargetProfileResource(value)
  return parsed === null ? undefined : parsed
}

function parseCurrentResume(
  value: unknown,
): ProfileOverview["current_resume"] | undefined {
  if (value === null || value === undefined) {
    return null
  }
  if (typeof value !== "object") {
    return undefined
  }
  const record = value as Record<string, unknown>
  if (
    !isNonEmptyString(record.id) ||
    !isNonEmptyString(record.original_file_name) ||
    !isNonEmptyString(record.media_type) ||
    typeof record.size_bytes !== "number" ||
    typeof record.revision !== "number" ||
    !isNonEmptyString(record.uploaded_at) ||
    !isNonEmptyString(record.updated_at)
  ) {
    return undefined
  }
  return {
    id: record.id,
    original_file_name: record.original_file_name,
    media_type: record.media_type,
    size_bytes: record.size_bytes,
    revision: record.revision,
    uploaded_at: record.uploaded_at,
    updated_at: record.updated_at,
  }
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

function optionalDisplayString(value: unknown): string | null {
  if (value === null || value === undefined || typeof value !== "string") {
    return null
  }
  const normalized = value.trim()
  return normalized === "" ? null : normalized
}
