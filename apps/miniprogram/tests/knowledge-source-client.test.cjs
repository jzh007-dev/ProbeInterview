const {
  AUTH_SESSION_CACHE_KEY,
  AUTH_SESSION_CACHE_SCHEMA_VERSION,
  resetAuthSessionMemoryForTests,
} = require("../miniprogram/services/auth-store.ts")
const {
  KnowledgeSourceApiError,
  fetchKnowledgeSources,
  uploadKnowledgeSource,
} = require("../miniprogram/services/knowledge-sources.ts")
const {resetTransportInvalidationForTests} = require("../miniprogram/services/transport.ts")
const {
  formatFileSize,
  quotaExhausted,
  sortNewestFirst,
} = require("../miniprogram/utils/knowledge-sources.ts")

const SESSION = {
  schemaVersion: AUTH_SESSION_CACHE_SCHEMA_VERSION,
  accessToken: "token-knowledge",
  expiresAt: "2099-01-01T00:00:00Z",
}

const QUOTA = {
  timezone: "Asia/Shanghai",
  daily_limit: 2,
  daily_used: 1,
  effective_source_limit: 100,
  effective_source_count: 1,
}
const SOURCE = {
  id: "source-1",
  original_filename: "notes.md",
  scope: "PRIVATE",
  processing_status: "PENDING_EXTRACTION",
  uploaded_at: "2026-09-30T06:00:00Z",
}

let storage

beforeEach(() => {
  storage = new Map()
  global.wx = {
    getStorageSync: (key) => storage.get(key),
    reLaunch: jest.fn(),
    removeStorageSync: (key) => storage.delete(key),
    request: jest.fn(),
    setStorageSync: (key, value) => storage.set(key, value),
    uploadFile: jest.fn(),
  }
  resetAuthSessionMemoryForTests()
  resetTransportInvalidationForTests()
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
})

test("sends authenticated list and multipart upload contracts", async () => {
  const request = jest.fn((options) => {
    expect(options.url).toBe(
      "http://127.0.0.1:8080/api/v1/me/knowledge-sources",
    )
    expect(options.method).toBe("GET")
    expect(options.header).toEqual({Authorization: "Bearer token-knowledge"})
    options.success({statusCode: 200, data: {quota: QUOTA, items: [SOURCE]}})
  })
  const upload = jest.fn((options) => {
    expect(options.url).toBe(
      "http://127.0.0.1:8080/api/v1/me/knowledge-sources",
    )
    expect(options).toMatchObject({
      filePath: "/tmp/notes.md",
      name: "file",
      formData: {
        scope: "PUBLIC",
        original_filename: "用户选择的笔记.md",
      },
    })
    expect(options.header).toEqual({
      Authorization: "Bearer token-knowledge",
      "Idempotency-Key": "upload-1",
    })
    expect(JSON.stringify(options)).not.toContain("access_key")
    expect(JSON.stringify(options)).not.toContain("oss")
    options.success({
      statusCode: 202,
      data: JSON.stringify({source: {...SOURCE, scope: "PUBLIC"}, quota: QUOTA}),
    })
  })
  global.wx.request = request
  global.wx.uploadFile = upload

  await expect(fetchKnowledgeSources()).resolves.toEqual({
    quota: QUOTA,
    items: [SOURCE],
  })
  await expect(
    uploadKnowledgeSource({
      filePath: "/tmp/notes.md",
      originalFilename: "用户选择的笔记.md",
      scope: "PUBLIC",
      idempotencyKey: "upload-1",
    }),
  ).resolves.toEqual({source: {...SOURCE, scope: "PUBLIC"}, quota: QUOTA})
})

test("rejects collection payloads that fail runtime validation", async () => {
  global.wx.request = jest.fn((options) => {
    options.success({
      statusCode: 200,
      data: {quota: QUOTA, items: [{...SOURCE, scope: "INTERNAL"}]},
    })
  })
  await expect(fetchKnowledgeSources()).rejects.toEqual(
    new KnowledgeSourceApiError("unknown_error"),
  )

  global.wx.request = jest.fn((options) => {
    options.success({statusCode: 200, data: {quota: QUOTA}})
  })
  await expect(fetchKnowledgeSources()).rejects.toEqual(
    new KnowledgeSourceApiError("unknown_error"),
  )
})

test("maps Problem Details codes to safe actionable errors", async () => {
  const privateDetail = "provider secret and object key"
  global.wx.request = jest.fn((options) =>
    options.success({
      statusCode: 429,
      data: {
        code: "daily_upload_limit_reached",
        detail: privateDetail,
        quota: {...QUOTA, daily_used: 2},
      },
    }),
  )
  await expect(fetchKnowledgeSources()).rejects.toEqual(
    new KnowledgeSourceApiError("daily_upload_limit_reached"),
  )
  await expect(fetchKnowledgeSources()).rejects.not.toHaveProperty(
    "message",
    privateDetail,
  )

  global.wx.uploadFile = jest.fn((options) =>
    options.success({
      statusCode: 503,
      data: JSON.stringify({
        code: "object_storage_unavailable",
        detail: privateDetail,
      }),
    }),
  )
  await expect(
    uploadKnowledgeSource({
      filePath: "/tmp/notes.md",
      originalFilename: "notes.md",
      scope: "PRIVATE",
      idempotencyKey: "upload-2",
    }),
  ).rejects.toEqual(new KnowledgeSourceApiError("object_storage_unavailable"))

  global.wx.request = jest.fn((options) => options.fail({errMsg: "secret"}))
  await expect(fetchKnowledgeSources()).rejects.toEqual(
    new KnowledgeSourceApiError("network_error"),
  )
})

test("surfaces session invalidation as the unauthorized error", async () => {
  global.wx.request = jest.fn((options) => {
    options.success({statusCode: 401, data: {code: "authentication_required"}})
  })

  await expect(fetchKnowledgeSources()).rejects.toEqual(
    new KnowledgeSourceApiError("unauthorized"),
  )

  // The shared transport has already cleared both caches and redirected.
  expect(storage.has(AUTH_SESSION_CACHE_KEY)).toBe(false)
  expect(global.wx.reLaunch).toHaveBeenCalledWith({url: "/pages/login/index"})
})

test("formats selection metadata, quota state, and stable newest-first ordering", () => {
  expect(formatFileSize(512)).toBe("512 B")
  expect(formatFileSize(2048)).toBe("2.0 KiB")
  expect(quotaExhausted(QUOTA)).toBe(false)
  expect(quotaExhausted({...QUOTA, daily_used: 2})).toBe(true)
  const items = [
    {...SOURCE, id: "a", uploaded_at: "2026-09-30T05:00:00Z"},
    {...SOURCE, id: "b", uploaded_at: "2026-09-30T06:00:00Z"},
    {...SOURCE, id: "c", uploaded_at: "2026-09-30T06:00:00Z"},
  ]
  expect(sortNewestFirst(items).map(({id}) => id)).toEqual(["c", "b", "a"])
})
