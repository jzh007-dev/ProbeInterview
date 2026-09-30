export interface WechatTargetProfileView {
  target_role: string
  relevant_experience_months: number
}

export interface WechatCurrentUserView {
  id: string
  nickname: string
  avatar_url: string | null
  avatar_url_expires_at: string | null
  default_target_profile: WechatTargetProfileView | null
}

export interface WechatAuthenticatedBootstrap {
  status: "authenticated"
  access_token: string
  expires_at: string
  current_user: WechatCurrentUserView
}

export interface WechatRegistrationRequiredBootstrap {
  status: "registration_required"
  registration_token: string
  expires_at: string
}

export type WechatBootstrapResponse =
  | WechatAuthenticatedBootstrap
  | WechatRegistrationRequiredBootstrap

export type LoginErrorCode =
  | "wechat_login_failed"
  | "network_error"
  | "unauthorized"
  | "request_failed"
  | "invalid_response"

export class LoginError extends Error {
  readonly code: LoginErrorCode
  readonly problemCode: string | null

  constructor(code: LoginErrorCode, problemCode: string | null = null) {
    super(describeLoginProblem(code, problemCode))
    this.name = "LoginError"
    this.code = code
    this.problemCode = problemCode
  }
}

const LOGIN_ERROR_MESSAGES: Record<LoginErrorCode, string> = {
  wechat_login_failed: "微信登录失败，请重试",
  network_error: "网络连接失败，请稍后重试",
  unauthorized: "登录状态已失效，请重新登录",
  request_failed: "操作失败，请稍后重试",
  invalid_response: "登录响应异常，请稍后重试",
}

const SAFE_PROBLEM_MESSAGES: Record<string, string> = {
  wechat_code_exchange_failed: "微信登录失败，请重试",
  wechat_service_unavailable: "微信服务暂时不可用，请稍后重试",
  registration_token_invalid: "注册凭证已过期，请重新登录",
  invalid_nickname: "昵称不合法，请输入 1 到 200 个字符",
  invalid_avatar: "头像文件不支持，请重新选择图片",
  storage_unavailable: "头像存储暂时不可用，请稍后重试",
}

function describeLoginProblem(
  code: LoginErrorCode,
  problemCode: string | null,
): string {
  if (problemCode !== null) {
    const safeMessage = SAFE_PROBLEM_MESSAGES[problemCode]
    if (safeMessage !== undefined) {
      return safeMessage
    }
  }
  return LOGIN_ERROR_MESSAGES[code]
}

export function describeLoginError(error: unknown): string {
  if (error instanceof LoginError) {
    return describeLoginProblem(error.code, error.problemCode)
  }
  return LOGIN_ERROR_MESSAGES.request_failed
}

export function parseWechatBootstrapResponse(
  value: unknown,
): WechatBootstrapResponse | null {
  if (typeof value !== "object" || value === null) {
    return null
  }
  const record = value as Record<string, unknown>

  if (record.status === "registration_required") {
    if (
      isNonEmptyString(record.registration_token) &&
      isNonEmptyString(record.expires_at)
    ) {
      return {
        status: "registration_required",
        registration_token: record.registration_token,
        expires_at: record.expires_at,
      }
    }
    return null
  }

  if (record.status !== "authenticated") {
    return null
  }
  if (
    !isNonEmptyString(record.access_token) ||
    !isNonEmptyString(record.expires_at)
  ) {
    return null
  }
  const currentUser = parseCurrentUserView(record.current_user)
  if (currentUser === null) {
    return null
  }
  return {
    status: "authenticated",
    access_token: record.access_token,
    expires_at: record.expires_at,
    current_user: currentUser,
  }
}

export function validateLoginNickname(nickname: string): string | null {
  const normalized = nickname.trim()
  if (!normalized || normalized.length > 200) {
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

function parseCurrentUserView(value: unknown): WechatCurrentUserView | null {
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

  const profile = parseTargetProfileView(record.default_target_profile)
  if (profile === undefined) {
    return null
  }

  return {
    id: record.id,
    nickname: record.nickname,
    avatar_url: avatarUrl,
    avatar_url_expires_at: avatarUrlExpiresAt,
    default_target_profile: profile,
  }
}

function parseTargetProfileView(
  value: unknown,
): WechatTargetProfileView | null | undefined {
  if (value === null || value === undefined) {
    return null
  }
  if (typeof value !== "object") {
    return undefined
  }
  const record = value as Record<string, unknown>
  if (!isNonEmptyString(record.target_role)) {
    return undefined
  }
  const months = record.relevant_experience_months
  if (
    typeof months !== "number" ||
    !Number.isInteger(months) ||
    months < 0
  ) {
    return undefined
  }
  return {target_role: record.target_role, relevant_experience_months: months}
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

function optionalDisplayString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null
  }
  if (typeof value !== "string") {
    return null
  }
  const normalized = value.trim()
  return normalized === "" ? null : normalized
}
