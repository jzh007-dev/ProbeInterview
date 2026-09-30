export type KnowledgeSourceScope = "PRIVATE" | "PUBLIC"

export interface KnowledgeSourceQuota {
  timezone: "Asia/Shanghai"
  daily_limit: number
  daily_used: number
  effective_source_limit: number
  effective_source_count: number
}

export interface KnowledgeSourceItem {
  id: string
  original_filename: string
  scope: KnowledgeSourceScope
  processing_status: "PENDING_EXTRACTION"
  uploaded_at: string
}

export interface KnowledgeSourceCollection {
  quota: KnowledgeSourceQuota
  items: KnowledgeSourceItem[]
}

export interface KnowledgeSourceUpload {
  source: KnowledgeSourceItem
  quota: KnowledgeSourceQuota
}

export interface ProblemDetails {
  status?: number
  code?: string
  quota?: KnowledgeSourceQuota
}

interface RequestResponse {
  statusCode: number
  data: unknown
}

interface RequestOptions {
  url: string
  method: "GET"
  success: (response: RequestResponse) => void
  fail: () => void
}

interface UploadResponse {
  statusCode: number
  data: string
}

interface UploadOptions {
  url: string
  filePath: string
  name: "file"
  formData: {
    scope: KnowledgeSourceScope
    original_filename: string
  }
  header: {"Idempotency-Key": string}
  success: (response: UploadResponse) => void
  fail: () => void
}

export type KnowledgeSourceRequest = (options: RequestOptions) => void
export type KnowledgeSourceUploader = (options: UploadOptions) => void

export type KnowledgeSourceErrorCode =
  | "daily_upload_limit_reached"
  | "effective_source_limit_reached"
  | "idempotency_conflict"
  | "invalid_knowledge_source"
  | "knowledge_source_too_large"
  | "network_error"
  | "object_storage_unavailable"
  | "public_knowledge_source_forbidden"
  | "unknown_error"

const ERROR_MESSAGES: Record<KnowledgeSourceErrorCode, string> = {
  daily_upload_limit_reached: "今日上传额度已用完，请明天再试",
  effective_source_limit_reached: "知识资料数量已达上限",
  idempotency_conflict: "本次上传标识已被其他文件使用，请重新选择",
  invalid_knowledge_source: "请选择有效的 UTF-8 Markdown 文件",
  knowledge_source_too_large: "Markdown 文件必须小于 500 KiB",
  network_error: "网络连接失败，请稍后重试",
  object_storage_unavailable: "资料存储暂时不可用，请稍后重试",
  public_knowledge_source_forbidden: "当前账号不能提交 public 资料",
  unknown_error: "请求失败，请稍后重试",
}

export class KnowledgeSourceApiError extends Error {
  readonly code: KnowledgeSourceErrorCode
  readonly quota: KnowledgeSourceQuota | null

  constructor(
    code: KnowledgeSourceErrorCode,
    quota: KnowledgeSourceQuota | null = null,
  ) {
    super(ERROR_MESSAGES[code])
    this.name = "KnowledgeSourceApiError"
    this.code = code
    this.quota = quota
  }
}

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8080"

export function fetchKnowledgeSources(
  request: KnowledgeSourceRequest = requestWithWechat,
  apiBaseUrl = DEFAULT_API_BASE_URL,
): Promise<KnowledgeSourceCollection> {
  return new Promise((resolve, reject) => {
    request({
      url: `${apiBaseUrl}/api/v1/me/knowledge-sources`,
      method: "GET",
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data as KnowledgeSourceCollection)
          return
        }
        reject(problemError(response.data))
      },
      fail() {
        reject(new KnowledgeSourceApiError("network_error"))
      },
    })
  })
}

export function uploadKnowledgeSource(
  input: {
    filePath: string
    originalFilename: string
    scope: KnowledgeSourceScope
    idempotencyKey: string
  },
  upload: KnowledgeSourceUploader = uploadWithWechat,
  apiBaseUrl = DEFAULT_API_BASE_URL,
): Promise<KnowledgeSourceUpload> {
  return new Promise((resolve, reject) => {
    upload({
      url: `${apiBaseUrl}/api/v1/me/knowledge-sources`,
      filePath: input.filePath,
      name: "file",
      formData: {
        scope: input.scope,
        original_filename: input.originalFilename,
      },
      header: {"Idempotency-Key": input.idempotencyKey},
      success(response) {
        let data: unknown
        try {
          data = JSON.parse(response.data)
        } catch {
          reject(new KnowledgeSourceApiError("unknown_error"))
          return
        }
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(data as KnowledgeSourceUpload)
          return
        }
        reject(problemError(data))
      },
      fail() {
        reject(new KnowledgeSourceApiError("network_error"))
      },
    })
  })
}

function problemError(value: unknown): KnowledgeSourceApiError {
  const problem =
    typeof value === "object" && value !== null ? (value as ProblemDetails) : {}
  const knownCodes = Object.keys(ERROR_MESSAGES) as KnowledgeSourceErrorCode[]
  const code = knownCodes.includes(problem.code as KnowledgeSourceErrorCode)
    ? (problem.code as KnowledgeSourceErrorCode)
    : problem.code === "public_knowledge_source_forbidden"
      ? "public_knowledge_source_forbidden"
      : "unknown_error"
  return new KnowledgeSourceApiError(code, problem.quota ?? null)
}

const requestWithWechat: KnowledgeSourceRequest = (options) => {
  wx.request({
    url: options.url,
    method: options.method,
    success(response) {
      options.success({statusCode: response.statusCode, data: response.data})
    },
    fail() {
      options.fail()
    },
  })
}

const uploadWithWechat: KnowledgeSourceUploader = (options) => {
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
