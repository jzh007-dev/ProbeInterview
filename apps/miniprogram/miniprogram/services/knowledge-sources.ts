import {
  requestJson,
  uploadMultipart,
  TransportError,
} from "./transport"

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

export type KnowledgeSourceErrorCode =
  | "daily_upload_limit_reached"
  | "effective_source_limit_reached"
  | "idempotency_conflict"
  | "invalid_knowledge_source"
  | "knowledge_source_too_large"
  | "network_error"
  | "object_storage_unavailable"
  | "public_knowledge_source_forbidden"
  | "unauthorized"
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
  unauthorized: "登录状态已失效，请重新登录",
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
const COLLECTION_ENDPOINT = "/api/v1/me/knowledge-sources"

function toApiError(error: unknown): KnowledgeSourceApiError {
  if (error instanceof TransportError) {
    if (error.code === "network_error") {
      return new KnowledgeSourceApiError("network_error")
    }
    if (error.code === "unauthorized") {
      return new KnowledgeSourceApiError("unauthorized")
    }
    if (
      error.problemCode !== null &&
      KNOWN_PROBLEM_CODES.has(error.problemCode)
    ) {
      return new KnowledgeSourceApiError(
        error.problemCode as KnowledgeSourceErrorCode,
      )
    }
  }
  return new KnowledgeSourceApiError("unknown_error")
}

const KNOWN_PROBLEM_CODES = new Set([
  "daily_upload_limit_reached",
  "effective_source_limit_reached",
  "idempotency_conflict",
  "invalid_knowledge_source",
  "knowledge_source_too_large",
  "object_storage_unavailable",
  "public_knowledge_source_forbidden",
])

export async function fetchKnowledgeSources(
  apiBaseUrl = DEFAULT_API_BASE_URL,
): Promise<KnowledgeSourceCollection> {
  let payload: unknown
  try {
    payload = await requestJson(
      {url: `${apiBaseUrl}${COLLECTION_ENDPOINT}`, method: "GET"},
      {authenticated: true},
    )
  } catch (error) {
    throw toApiError(error)
  }
  const parsed = parseCollection(payload)
  if (parsed === null) {
    throw new KnowledgeSourceApiError("unknown_error")
  }
  return parsed
}

export async function uploadKnowledgeSource(
  input: {
    filePath: string
    originalFilename: string
    scope: KnowledgeSourceScope
    idempotencyKey: string
  },
  apiBaseUrl = DEFAULT_API_BASE_URL,
): Promise<KnowledgeSourceUpload> {
  let payload: unknown
  try {
    payload = await uploadMultipart(
      {
        url: `${apiBaseUrl}${COLLECTION_ENDPOINT}`,
        filePath: input.filePath,
        name: "file",
        formData: {
          scope: input.scope,
          original_filename: input.originalFilename,
        },
        header: {"Idempotency-Key": input.idempotencyKey},
      },
      {authenticated: true},
    )
  } catch (error) {
    throw toApiError(error)
  }
  const parsed = parseUpload(payload)
  if (parsed === null) {
    throw new KnowledgeSourceApiError("unknown_error")
  }
  return parsed
}

function parseCollection(value: unknown): KnowledgeSourceCollection | null {
  if (typeof value !== "object" || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  const quota = parseQuota(record.quota)
  if (quota === null || !Array.isArray(record.items)) {
    return null
  }
  const items: KnowledgeSourceItem[] = []
  for (const entry of record.items) {
    const item = parseItem(entry)
    if (item === null) {
      return null
    }
    items.push(item)
  }
  return {quota, items}
}

function parseUpload(value: unknown): KnowledgeSourceUpload | null {
  if (typeof value !== "object" || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  const quota = parseQuota(record.quota)
  const item = parseItem(record.source)
  if (quota === null || item === null) {
    return null
  }
  return {source: item, quota}
}

function parseQuota(value: unknown): KnowledgeSourceQuota | null {
  if (typeof value !== "object" || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  if (
    record.timezone !== "Asia/Shanghai" ||
    !isFiniteNumber(record.daily_limit) ||
    !isFiniteNumber(record.daily_used) ||
    !isFiniteNumber(record.effective_source_limit) ||
    !isFiniteNumber(record.effective_source_count)
  ) {
    return null
  }
  return {
    timezone: "Asia/Shanghai",
    daily_limit: record.daily_limit,
    daily_used: record.daily_used,
    effective_source_limit: record.effective_source_limit,
    effective_source_count: record.effective_source_count,
  }
}

function parseItem(value: unknown): KnowledgeSourceItem | null {
  if (typeof value !== "object" || value === null) {
    return null
  }
  const record = value as Record<string, unknown>
  if (
    typeof record.id !== "string" ||
    record.id === "" ||
    typeof record.original_filename !== "string" ||
    record.original_filename === "" ||
    (record.scope !== "PRIVATE" && record.scope !== "PUBLIC") ||
    record.processing_status !== "PENDING_EXTRACTION" ||
    typeof record.uploaded_at !== "string" ||
    record.uploaded_at === ""
  ) {
    return null
  }
  return {
    id: record.id,
    original_filename: record.original_filename,
    scope: record.scope,
    processing_status: "PENDING_EXTRACTION",
    uploaded_at: record.uploaded_at,
  }
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}
