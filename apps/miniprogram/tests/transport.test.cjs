const {
  AUTH_SESSION_CACHE_KEY,
  AUTH_SESSION_CACHE_SCHEMA_VERSION,
  resetAuthSessionMemoryForTests,
} = require("../miniprogram/services/auth-store.ts")
const {
  CURRENT_USER_CACHE_KEY,
  CURRENT_USER_CACHE_SCHEMA_VERSION,
} = require("../miniprogram/services/current-user-store.ts")
const {
  TransportError,
  requestJson,
  resetTransportInvalidationForTests,
  uploadMultipart,
} = require("../miniprogram/services/transport.ts")

const SESSION = {
  schemaVersion: AUTH_SESSION_CACHE_SCHEMA_VERSION,
  accessToken: "token-abc",
  expiresAt: "2099-01-01T00:00:00Z",
}

const SNAPSHOT = {
  schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
  userId: "user-9",
  nickname: "Lin Qiao",
  avatarUrl: null,
  avatarUrlExpiresAt: null,
  defaultTargetProfile: null,
}

let storage
let redirectCalls

function okRequest(response) {
  return jest.fn((options) => {
    options.success({statusCode: 200, data: response})
  })
}

beforeEach(() => {
  storage = new Map()
  redirectCalls = 0
  global.wx = {
    getStorageSync: jest.fn((key) => storage.get(key)),
    reLaunch: jest.fn(() => {
      redirectCalls += 1
    }),
    removeStorageSync: jest.fn((key) => storage.delete(key)),
    request: jest.fn(),
    setStorageSync: jest.fn((key, value) => storage.set(key, value)),
    uploadFile: jest.fn(),
  }
  resetTransportInvalidationForTests()
  resetAuthSessionMemoryForTests()
})

test("attaches the bearer token only to protected calls", async () => {
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)

  const publicRequest = okRequest({status: "ok"})
  await requestJson(
    {url: "http://api/exchanges", method: "POST", data: {code: "c"}},
    {authenticated: false},
    publicRequest,
  )
  expect(publicRequest.mock.calls[0][0].header).toEqual({})

  const protectedRequest = okRequest({status: "ok"})
  await requestJson(
    {url: "http://api/me/overview", method: "GET"},
    {authenticated: true},
    protectedRequest,
  )
  expect(protectedRequest.mock.calls[0][0].header).toEqual({
    Authorization: "Bearer token-abc",
  })
})

test("never lets callers supply or override the Authorization header", async () => {
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)

  const protectedRequest = okRequest({})
  await requestJson(
    {
      url: "http://api/me/overview",
      method: "GET",
      header: {Authorization: "Bearer forged-token", "Idempotency-Key": "key-1"},
    },
    {authenticated: true},
    protectedRequest,
  )
  expect(protectedRequest.mock.calls[0][0].header).toEqual({
    Authorization: "Bearer token-abc",
    "Idempotency-Key": "key-1",
  })

  const publicRequest = okRequest({})
  await requestJson(
    {
      url: "http://api/registrations",
      method: "POST",
      header: {Authorization: "Bearer forged-token"},
    },
    {authenticated: false},
    publicRequest,
  )
  expect(publicRequest.mock.calls[0][0].header).toEqual({})
})

test("keeps idempotency keys and form fields on multipart uploads", async () => {
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)

  const upload = jest.fn((options) => {
    options.success({statusCode: 201, data: JSON.stringify({source: {id: "s-1"}})})
  })
  await expect(
    uploadMultipart(
      {
        url: "http://api/me/knowledge-sources",
        filePath: "wxfile://tmp.md",
        name: "file",
        formData: {scope: "PRIVATE", original_filename: "notes.md"},
        header: {"Idempotency-Key": "key-42"},
      },
      {authenticated: true},
      upload,
    ),
  ).resolves.toEqual({source: {id: "s-1"}})

  expect(upload.mock.calls[0][0].header).toEqual({
    Authorization: "Bearer token-abc",
    "Idempotency-Key": "key-42",
  })
  expect(upload.mock.calls[0][0].formData).toEqual({
    scope: "PRIVATE",
    original_filename: "notes.md",
  })
})

test("fails a protected call without a session before any network request", async () => {
  storage.set(CURRENT_USER_CACHE_KEY, SNAPSHOT)
  const request = okRequest({})

  await expect(
    requestJson({url: "http://api/me/overview", method: "GET"}, {authenticated: true}, request),
  ).rejects.toEqual(new TransportError("unauthorized"))

  expect(request).not.toHaveBeenCalled()
  expect(storage.has(AUTH_SESSION_CACHE_KEY)).toBe(false)
  expect(storage.has(CURRENT_USER_CACHE_KEY)).toBe(false)
  expect(redirectCalls).toBe(1)
})

test("invalidates both caches once and re-enters the login page on 401", async () => {
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
  storage.set(CURRENT_USER_CACHE_KEY, SNAPSHOT)
  const request = jest.fn((options) => {
    options.success({statusCode: 401, data: {code: "authentication_required"}})
  })

  await expect(
    requestJson({url: "http://api/me/overview", method: "GET"}, {authenticated: true}, request),
  ).rejects.toEqual(new TransportError("unauthorized", 401))

  expect(request).toHaveBeenCalledTimes(1)
  expect(storage.has(AUTH_SESSION_CACHE_KEY)).toBe(false)
  expect(storage.has(CURRENT_USER_CACHE_KEY)).toBe(false)
  expect(redirectCalls).toBe(1)
})

test("collapses concurrent 401 responses into a single invalidation", async () => {
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
  storage.set(CURRENT_USER_CACHE_KEY, SNAPSHOT)
  let removals = 0
  global.wx.reLaunch = jest.fn(() => {
    redirectCalls += 1
  })
  global.wx.removeStorageSync = jest.fn((key) => {
    if (storage.delete(key)) {
      removals += 1
    }
  })
  const request = jest.fn((options) => {
    options.success({statusCode: 401, data: {}})
  })

  const first = requestJson({url: "http://api/a", method: "GET"}, {authenticated: true}, request)
  const second = requestJson({url: "http://api/b", method: "GET"}, {authenticated: true}, request)
  await expect(first).rejects.toBeInstanceOf(TransportError)
  await expect(second).rejects.toBeInstanceOf(TransportError)

  expect(removals).toBe(2)
  expect(redirectCalls).toBe(1)
})

test("starts no silent login and no retry when invalidating a session", async () => {
  global.wx.login = jest.fn()
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
  const request = jest.fn((options) => {
    options.success({statusCode: 401, data: {}})
  })

  await expect(
    requestJson({url: "http://api/me/overview", method: "GET"}, {authenticated: true}, request),
  ).rejects.toBeInstanceOf(TransportError)
  await new Promise((resolve) => setTimeout(resolve, 0))

  expect(request).toHaveBeenCalledTimes(1)
  expect(global.wx.login).not.toHaveBeenCalled()
})

test("maps public 401 responses to a domain failure without invalidation", async () => {
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
  storage.set(CURRENT_USER_CACHE_KEY, SNAPSHOT)
  const request = jest.fn((options) => {
    options.success({statusCode: 401, data: {code: "registration_token_invalid"}})
  })

  await expect(
    requestJson(
      {url: "http://api/auth/wechat/registrations", method: "POST"},
      {authenticated: false},
      request,
    ),
  ).rejects.toEqual(
    new TransportError("request_failed", 401, "registration_token_invalid"),
  )
  expect(storage.has(AUTH_SESSION_CACHE_KEY)).toBe(true)
  expect(redirectCalls).toBe(0)
})

test("sanitizes problem details and network failures", async () => {
  const problemRequest = jest.fn((options) => {
    options.success({
      statusCode: 422,
      data: {detail: "secret upstream detail", code: "invalid_nickname"},
    })
  })
  await expect(
    requestJson({url: "http://api/x", method: "POST"}, {authenticated: false}, problemRequest),
  ).rejects.toEqual(new TransportError("request_failed", 422, "invalid_nickname"))

  const opaqueRequest = jest.fn((options) => {
    options.success({statusCode: 503, data: {detail: "secret upstream detail"}})
  })
  await expect(
    requestJson({url: "http://api/x", method: "GET"}, {authenticated: false}, opaqueRequest),
  ).rejects.toEqual(new TransportError("request_failed", 503, null))

  const failingRequest = jest.fn((options) => {
    options.fail({errMsg: "request:fail secret"})
  })
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
  await expect(
    requestJson({url: "http://api/x", method: "GET"}, {authenticated: true}, failingRequest),
  ).rejects.toEqual(new TransportError("network_error"))
})

test("rejects multipart bodies that are not JSON", async () => {
  const upload = jest.fn((options) => {
    options.success({statusCode: 200, data: "<html>not json</html>"})
  })

  await expect(
    uploadMultipart(
      {url: "http://api/upload", filePath: "p", name: "file"},
      {authenticated: false},
      upload,
    ),
  ).rejects.toEqual(new TransportError("invalid_response", 200))
})
