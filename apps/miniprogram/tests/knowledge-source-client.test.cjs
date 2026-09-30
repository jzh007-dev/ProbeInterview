const {
  KnowledgeSourceApiError,
  fetchKnowledgeSources,
  uploadKnowledgeSource,
} = require("../miniprogram/services/knowledge-sources.ts")
const {
  formatFileSize,
  quotaExhausted,
  sortNewestFirst,
} = require("../miniprogram/utils/knowledge-sources.ts")

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

test("maps list and multipart upload contracts without OSS credentials", async () => {
  const request = jest.fn((options) => {
    expect(options.url).toBe(
      "http://127.0.0.1:8080/api/v1/me/knowledge-sources",
    )
    expect(options.method).toBe("GET")
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
      header: {"Idempotency-Key": "upload-1"},
    })
    expect(JSON.stringify(options)).not.toContain("access_key")
    expect(JSON.stringify(options)).not.toContain("oss")
    options.success({
      statusCode: 202,
      data: JSON.stringify({source: {...SOURCE, scope: "PUBLIC"}, quota: QUOTA}),
    })
  })

  await expect(fetchKnowledgeSources(request)).resolves.toEqual({
    quota: QUOTA,
    items: [SOURCE],
  })
  await expect(
    uploadKnowledgeSource(
      {
        filePath: "/tmp/notes.md",
        originalFilename: "用户选择的笔记.md",
        scope: "PUBLIC",
        idempotencyKey: "upload-1",
      },
      upload,
    ),
  ).resolves.toEqual({source: {...SOURCE, scope: "PUBLIC"}, quota: QUOTA})
})

test("maps Problem Details codes to safe actionable errors and quota context", async () => {
  const privateDetail = "provider secret and object key"
  const request = (options) =>
    options.success({
      statusCode: 429,
      data: {
        code: "daily_upload_limit_reached",
        detail: privateDetail,
        quota: {...QUOTA, daily_used: 2},
      },
    })
  const upload = (options) =>
    options.success({
      statusCode: 503,
      data: JSON.stringify({
        code: "object_storage_unavailable",
        detail: privateDetail,
      }),
    })

  await expect(fetchKnowledgeSources(request)).rejects.toEqual(
    new KnowledgeSourceApiError(
      "daily_upload_limit_reached",
      {...QUOTA, daily_used: 2},
    ),
  )
  await expect(
    uploadKnowledgeSource(
      {
        filePath: "/tmp/notes.md",
        originalFilename: "notes.md",
        scope: "PRIVATE",
        idempotencyKey: "upload-2",
      },
      upload,
    ),
  ).rejects.toEqual(new KnowledgeSourceApiError("object_storage_unavailable"))
  await expect(fetchKnowledgeSources(request)).rejects.not.toHaveProperty(
    "message",
    privateDetail,
  )
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
