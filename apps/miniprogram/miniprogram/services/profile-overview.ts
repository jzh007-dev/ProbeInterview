import {
  parseProfileOverview,
  parseTargetProfileResource,
} from "../utils/profile-overview"
import {requestJson, TransportError} from "./transport"

export interface TargetProfileOverview {
  id: string
  target_role: string
  relevant_experience_months: number
}

export interface CurrentResumeOverview {
  id: string
  original_file_name: string
  media_type: string
  size_bytes: number
  revision: number
  uploaded_at: string
  updated_at: string
}

export interface ProfileOverview {
  id: string
  nickname: string
  avatar_url: string | null
  avatar_url_expires_at: string | null
  default_target_profile: TargetProfileOverview | null
  current_resume: CurrentResumeOverview | null
  recent_scores: unknown[]
}

export interface TargetProfileWriteInput {
  targetRole: string
  relevantExperienceMonths: number
}

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8080"
const OVERVIEW_ENDPOINT = "/api/v1/me/overview"
const DEFAULT_TARGET_PROFILE_ENDPOINT = "/api/v1/me/default-target-profile"

export async function fetchProfileOverview(
  apiBaseUrl = DEFAULT_API_BASE_URL,
): Promise<ProfileOverview> {
  const payload = await requestJson(
    {url: `${apiBaseUrl}${OVERVIEW_ENDPOINT}`, method: "GET"},
    {authenticated: true},
  )
  const overview = parseProfileOverview(payload)
  if (overview === null) {
    throw new TransportError("invalid_response")
  }
  return overview
}

export async function putDefaultTargetProfile(
  input: TargetProfileWriteInput,
  apiBaseUrl = DEFAULT_API_BASE_URL,
): Promise<TargetProfileOverview> {
  const payload = await requestJson(
    {
      url: `${apiBaseUrl}${DEFAULT_TARGET_PROFILE_ENDPOINT}`,
      method: "PUT",
      data: {
        target_role: input.targetRole,
        relevant_experience_months: input.relevantExperienceMonths,
      },
    },
    {authenticated: true},
  )
  const profile = parseTargetProfileResource(payload)
  if (profile === null) {
    throw new TransportError("invalid_response")
  }
  return profile
}

const SAFE_PROFILE_PROBLEM_MESSAGES: Record<string, string> = {
  invalid_target_role: "目标岗位需为 1 到 200 个字符",
  validation_error: "请检查目标岗位与经验月数的取值",
}

export function describeProfileError(error: unknown): string {
  if (error instanceof TransportError) {
    if (error.problemCode !== null) {
      const safeMessage = SAFE_PROFILE_PROBLEM_MESSAGES[error.problemCode]
      if (safeMessage !== undefined) {
        return safeMessage
      }
    }
    return error.message
  }
  return "请求失败，请稍后重试"
}
