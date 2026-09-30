import {
  AUTH_SESSION_CACHE_SCHEMA_VERSION,
  clearAuthSession,
  writeAuthSession,
  type AuthSessionSnapshot,
} from "./auth-store"
import {
  currentUserSnapshotFromResource,
  writeCurrentUserSnapshot,
} from "./current-user-store"
import {
  requestJson,
  uploadMultipart,
  TransportError,
  type TransportPayload,
} from "./transport"
import {
  LoginError,
  parseWechatBootstrapResponse,
  validateLoginNickname,
  type WechatAuthenticatedBootstrap,
  type WechatBootstrapResponse,
} from "../utils/login"

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8080"
const EXCHANGE_ENDPOINT = "/api/v1/auth/wechat/exchanges"
const REGISTRATION_ENDPOINT = "/api/v1/auth/wechat/registrations"
const AVATAR_REGISTRATION_ENDPOINT = "/api/v1/auth/wechat/avatar-registrations"

export interface LoginCoordinatorDeps {
  invokeWxLogin: (options: {
    success: (response: {code?: string}) => void
    fail: () => void
  }) => void
  requestJson: typeof requestJson
  uploadMultipart: typeof uploadMultipart
  writeAuthSession: (session: AuthSessionSnapshot) => AuthSessionSnapshot
  writeCurrentUserSnapshot: typeof writeCurrentUserSnapshot
  clearAuthSession: () => void
}

export function defaultLoginCoordinatorDeps(): LoginCoordinatorDeps {
  return {
    invokeWxLogin(options) {
      wx.login(options)
    },
    requestJson,
    uploadMultipart,
    writeAuthSession,
    writeCurrentUserSnapshot,
    clearAuthSession,
  }
}

export type StartWechatLoginResult =
  | {kind: "authenticated"}
  | {kind: "registration_required"; registrationToken: string; expiresAt: string}

function wxLoginCode(deps: LoginCoordinatorDeps): Promise<string> {
  return new Promise((resolve, reject) => {
    deps.invokeWxLogin({
      success(response) {
        const code = typeof response?.code === "string" ? response.code : ""
        if (code === "") {
          reject(new LoginError("wechat_login_failed"))
          return
        }
        resolve(code)
      },
      fail() {
        reject(new LoginError("wechat_login_failed"))
      },
    })
  })
}

function transportToLoginError(error: unknown): LoginError {
  if (error instanceof TransportError) {
    if (error.code === "network_error" || error.code === "unauthorized") {
      return new LoginError(error.code)
    }
    return new LoginError("request_failed", error.problemCode)
  }
  return new LoginError("request_failed")
}

async function bootstrapResponse(
  call: {url: string; method: "POST"; data?: TransportPayload},
  deps: LoginCoordinatorDeps,
): Promise<WechatBootstrapResponse> {
  let payload: unknown
  try {
    payload = await deps.requestJson(call, {authenticated: false})
  } catch (error) {
    throw transportToLoginError(error)
  }
  const parsed = parseWechatBootstrapResponse(payload)
  if (parsed === null) {
    throw new LoginError("invalid_response")
  }
  return parsed
}

function writeSessionPair(
  response: WechatAuthenticatedBootstrap,
  deps: LoginCoordinatorDeps,
): void {
  deps.writeAuthSession({
    schemaVersion: AUTH_SESSION_CACHE_SCHEMA_VERSION,
    accessToken: response.access_token,
    expiresAt: response.expires_at,
  })
  try {
    deps.writeCurrentUserSnapshot(
      currentUserSnapshotFromResource(response.current_user),
    )
  } catch {
    deps.clearAuthSession()
    throw new LoginError("invalid_response")
  }
}

export async function startWechatLogin(
  deps: LoginCoordinatorDeps = defaultLoginCoordinatorDeps(),
): Promise<StartWechatLoginResult> {
  const code = await wxLoginCode(deps)
  const response = await bootstrapResponse(
    {url: `${DEFAULT_API_BASE_URL}${EXCHANGE_ENDPOINT}`, method: "POST", data: {code}},
    deps,
  )
  if (response.status === "registration_required") {
    return {
      kind: "registration_required",
      registrationToken: response.registration_token,
      expiresAt: response.expires_at,
    }
  }
  writeSessionPair(response, deps)
  return {kind: "authenticated"}
}

export async function completeRegistration(
  input: {
    registrationToken: string
    nickname: string
    avatarFilePath?: string | null
  },
  deps: LoginCoordinatorDeps = defaultLoginCoordinatorDeps(),
): Promise<void> {
  const nickname = validateLoginNickname(input.nickname)
  if (nickname === null) {
    throw new LoginError("request_failed", "invalid_nickname")
  }

  let payload: unknown
  try {
    payload = input.avatarFilePath
      ? await deps.uploadMultipart(
          {
            url: `${DEFAULT_API_BASE_URL}${AVATAR_REGISTRATION_ENDPOINT}`,
            filePath: input.avatarFilePath,
            name: "file",
            formData: {
              registration_token: input.registrationToken,
              nickname,
            },
          },
          {authenticated: false},
        )
      : await deps.requestJson(
          {
            url: `${DEFAULT_API_BASE_URL}${REGISTRATION_ENDPOINT}`,
            method: "POST",
            data: {
              registration_token: input.registrationToken,
              nickname,
            },
          },
          {authenticated: false},
        )
  } catch (error) {
    throw transportToLoginError(error)
  }
  const parsed = parseWechatBootstrapResponse(payload)
  if (parsed === null || parsed.status !== "authenticated") {
    throw new LoginError("invalid_response")
  }
  writeSessionPair(parsed, deps)
}
