import {clearAuthState} from "./auth-state"
import {readAuthSession} from "./auth-store"

const LOGIN_PAGE_PATH = "/pages/login/index"

export type TransportErrorCode =
  | "network_error"
  | "unauthorized"
  | "request_failed"
  | "invalid_response"

const TRANSPORT_ERROR_MESSAGES: Record<TransportErrorCode, string> = {
  network_error: "网络连接失败，请稍后重试",
  unauthorized: "登录状态已失效，请重新登录",
  request_failed: "请求失败，请稍后重试",
  invalid_response: "服务响应异常，请稍后重试",
}

export class TransportError extends Error {
  readonly code: TransportErrorCode
  readonly statusCode: number | null
  readonly problemCode: string | null

  constructor(
    code: TransportErrorCode,
    statusCode: number | null = null,
    problemCode: string | null = null,
  ) {
    super(TRANSPORT_ERROR_MESSAGES[code])
    this.name = "TransportError"
    this.code = code
    this.statusCode = statusCode
    this.problemCode = problemCode
  }
}

export type TransportMethod = "GET" | "POST" | "PUT" | "DELETE"

export type TransportPayload = string | Record<string, unknown> | ArrayBuffer

export interface TransportRequestOptions {
  url: string
  method: TransportMethod
  data?: TransportPayload
  header?: Record<string, string>
}

export interface TransportUploadOptions {
  url: string
  filePath: string
  name: string
  formData?: Record<string, string>
  header?: Record<string, string>
}

export interface TransportCall {
  authenticated: boolean
}

interface TransportResponse {
  statusCode: number
  data: unknown
}

export type TransportRequester = (options: {
  url: string
  method: TransportMethod
  data?: TransportPayload
  header: Record<string, string>
  success: (response: TransportResponse) => void
  fail: () => void
}) => void

export type TransportUploader = (options: {
  url: string
  filePath: string
  name: string
  formData?: Record<string, string>
  header: Record<string, string>
  success: (response: TransportResponse) => void
  fail: () => void
}) => void

const wechatJsonRequest: TransportRequester = (options) => {
  wx.request({
    url: options.url,
    method: options.method,
    data: options.data,
    header: options.header,
    success(response) {
      options.success({statusCode: response.statusCode, data: response.data})
    },
    fail() {
      options.fail()
    },
  })
}

const wechatMultipartUpload: TransportUploader = (options) => {
  wx.uploadFile({
    url: options.url,
    filePath: options.filePath,
    name: options.name,
    formData: options.formData,
    header: options.header,
    success(response) {
      options.success({statusCode: response.statusCode, data: response.data})
    },
    fail() {
      options.fail()
    },
  })
}

function redirectToLoginPage(): void {
  wx.reLaunch({url: LOGIN_PAGE_PATH})
}

let sessionInvalidation: Promise<void> | null = null

function invalidateSessionOnce(redirect: () => void): Promise<void> {
  if (sessionInvalidation === null) {
    sessionInvalidation = Promise.resolve()
      .then(() => {
        clearAuthState()
        redirect()
      })
      .catch(() => undefined)
      .finally(() => {
        sessionInvalidation = null
      })
  }
  return sessionInvalidation
}

export function resetTransportInvalidationForTests(): void {
  sessionInvalidation = null
}

function extractProblemCode(data: unknown): string | null {
  if (typeof data !== "object" || data === null) {
    return null
  }
  const code = (data as Record<string, unknown>).code
  return typeof code === "string" && code.length > 0 ? code : null
}

function responseFailure(
  statusCode: number,
  data: unknown,
  call: TransportCall,
  redirect: () => void,
): TransportError {
  if (statusCode === 401 && call.authenticated) {
    void invalidateSessionOnce(redirect)
    return new TransportError("unauthorized", statusCode)
  }
  return new TransportError("request_failed", statusCode, extractProblemCode(data))
}

function baseHeader(callerHeader?: Record<string, string>): Record<string, string> {
  const header: Record<string, string> = {...(callerHeader ?? {})}
  delete header.Authorization
  return header
}

async function authorizedHeader(
  call: TransportCall,
  callerHeader: Record<string, string> | undefined,
  redirect: () => void,
): Promise<Record<string, string>> {
  const header = baseHeader(callerHeader)
  if (!call.authenticated) {
    return header
  }

  const session = readAuthSession()
  if (session === null) {
    void invalidateSessionOnce(redirect)
    throw new TransportError("unauthorized")
  }
  header.Authorization = `Bearer ${session.accessToken}`
  return header
}

function parseMultipartBody(data: unknown): {ok: true; value: unknown} | {ok: false} {
  if (typeof data !== "string") {
    return {ok: true, value: data}
  }
  try {
    return {ok: true, value: JSON.parse(data)}
  } catch {
    return {ok: false}
  }
}

export function requestJson(
  options: TransportRequestOptions,
  call: TransportCall,
  request: TransportRequester = wechatJsonRequest,
  redirect: () => void = redirectToLoginPage,
): Promise<unknown> {
  return authorizedHeader(call, options.header, redirect).then(
    (header) =>
      new Promise<unknown>((resolve, reject) => {
        request({
          url: options.url,
          method: options.method,
          data: options.data,
          header,
          success(response) {
            if (response.statusCode >= 200 && response.statusCode < 300) {
              resolve(response.data)
              return
            }
            reject(responseFailure(response.statusCode, response.data, call, redirect))
          },
          fail() {
            reject(new TransportError("network_error"))
          },
        })
      }),
  )
}

export function uploadMultipart(
  options: TransportUploadOptions,
  call: TransportCall,
  upload: TransportUploader = wechatMultipartUpload,
  redirect: () => void = redirectToLoginPage,
): Promise<unknown> {
  return authorizedHeader(call, options.header, redirect).then(
    (header) =>
      new Promise<unknown>((resolve, reject) => {
        upload({
          url: options.url,
          filePath: options.filePath,
          name: options.name,
          formData: options.formData,
          header,
          success(response) {
            const body = parseMultipartBody(response.data)
            if (!body.ok) {
              reject(new TransportError("invalid_response", response.statusCode))
              return
            }
            if (response.statusCode >= 200 && response.statusCode < 300) {
              resolve(body.value)
              return
            }
            reject(responseFailure(response.statusCode, body.value, call, redirect))
          },
          fail() {
            reject(new TransportError("network_error"))
          },
        })
      }),
  )
}
