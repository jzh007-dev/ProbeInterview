const {
  AUTH_SESSION_CACHE_KEY,
  AUTH_SESSION_CACHE_SCHEMA_VERSION,
  resetAuthSessionMemoryForTests,
} = require("../miniprogram/services/auth-store.ts")
const {
  CURRENT_USER_CACHE_KEY,
  CURRENT_USER_CACHE_SCHEMA_VERSION,
  resetCurrentUserMemoryForTests,
} = require("../miniprogram/services/current-user-store.ts")
const {
  completeRegistration,
  startWechatLogin,
} = require("../miniprogram/services/login-coordinator.ts")
const {
  LoginError,
  validateLoginNickname,
} = require("../miniprogram/utils/login.ts")
const {
  TransportError,
} = require("../miniprogram/services/transport.ts")

const AUTHENTICATED_RESPONSE = {
  status: "authenticated",
  access_token: "token-abc",
  expires_at: "2099-01-01T00:00:00Z",
  current_user: {
    id: "user-9",
    nickname: "Lin Qiao",
    avatar_url: null,
    avatar_url_expires_at: null,
    default_target_profile: null,
  },
}

const REGISTRATION_REQUIRED_RESPONSE = {
  status: "registration_required",
  registration_token: "reg-token-1",
  expires_at: "2026-10-01T10:00:00Z",
}

let storage
let wxLoginCalls
let requestCalls
let uploadCalls

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

function makeDeps(overrides = {}) {
  return {
    invokeWxLogin: jest.fn((options) => {
      wxLoginCalls.push(options)
      options.success({code: "wx-code-1"})
    }),
    requestJson: jest.fn((options) => {
      requestCalls.push(options)
      return Promise.resolve({status: "ok"})
    }),
    uploadMultipart: jest.fn(() => Promise.resolve({status: "ok"})),
    writeAuthSession: jest.fn((session) => session),
    writeCurrentUserSnapshot: jest.fn((snapshot) => snapshot),
    clearAuthSession: jest.fn(),
    ...overrides,
  }
}

beforeEach(() => {
  storage = new Map()
  wxLoginCalls = []
  requestCalls = []
  uploadCalls = []
  global.wx = {
    getStorageSync: jest.fn((key) => storage.get(key)),
    removeStorageSync: jest.fn((key) => storage.delete(key)),
    setStorageSync: jest.fn((key, value) => storage.set(key, value)),
  }
  resetAuthSessionMemoryForTests()
  resetCurrentUserMemoryForTests()
})

test("exchanges a code, validates both resources, then writes both caches", async () => {
  const deps = makeDeps({
    requestJson: jest.fn((options) => {
      requestCalls.push(options)
      return Promise.resolve(AUTHENTICATED_RESPONSE)
    }),
  })

  await expect(startWechatLogin(deps)).resolves.toEqual({kind: "authenticated"})

  expect(deps.invokeWxLogin).toHaveBeenCalledTimes(1)
  expect(requestCalls[0]).toEqual({
    url: "http://127.0.0.1:8080/api/v1/auth/wechat/exchanges",
    method: "POST",
    data: {code: "wx-code-1"},
  })
  expect(deps.writeAuthSession).toHaveBeenCalledWith({
    schemaVersion: AUTH_SESSION_CACHE_SCHEMA_VERSION,
    accessToken: "token-abc",
    expiresAt: "2099-01-01T00:00:00Z",
  })
  expect(deps.writeCurrentUserSnapshot).toHaveBeenCalledTimes(1)
})

test("returns the registration credential without touching any cache", async () => {
  const deps = makeDeps({
    requestJson: jest.fn(() =>
      Promise.resolve(REGISTRATION_REQUIRED_RESPONSE),
    ),
  })

  await expect(startWechatLogin(deps)).resolves.toEqual({
    kind: "registration_required",
    registrationToken: "reg-token-1",
    expiresAt: "2026-10-01T10:00:00Z",
  })

  expect(deps.writeAuthSession).not.toHaveBeenCalled()
  expect(deps.writeCurrentUserSnapshot).not.toHaveBeenCalled()
  expect(storage.size).toBe(0)
})

test("rejects malformed responses before writing any cache", async () => {
  const malformedResponses = [
    {},
    {status: "authenticated", access_token: "", expires_at: "x", current_user: {}},
    {...AUTHENTICATED_RESPONSE, current_user: {...AUTHENTICATED_RESPONSE.current_user, id: ""}},
    {
      ...AUTHENTICATED_RESPONSE,
      current_user: {
        ...AUTHENTICATED_RESPONSE.current_user,
        avatar_url: "https://example.invalid/a.png",
        avatar_url_expires_at: null,
      },
    },
    {
      ...AUTHENTICATED_RESPONSE,
      current_user: {
        ...AUTHENTICATED_RESPONSE.current_user,
        default_target_profile: {target_role: "Role", relevant_experience_months: -1},
      },
    },
    {status: "registration_required", registration_token: "t", expires_at: ""},
  ]

  for (const response of malformedResponses) {
    const deps = makeDeps({requestJson: jest.fn(() => Promise.resolve(response))})
    await expect(startWechatLogin(deps)).rejects.toEqual(
      new LoginError("invalid_response"),
    )
    expect(deps.writeAuthSession).not.toHaveBeenCalled()
    expect(deps.writeCurrentUserSnapshot).not.toHaveBeenCalled()
  }
})

test("rolls the token write back when the display cache write fails", async () => {
  const deps = makeDeps({
    requestJson: jest.fn(() => Promise.resolve(AUTHENTICATED_RESPONSE)),
    writeCurrentUserSnapshot: jest.fn(() => {
      throw new Error("storage full")
    }),
  })

  await expect(startWechatLogin(deps)).rejects.toEqual(
    new LoginError("invalid_response"),
  )
  expect(deps.writeAuthSession).toHaveBeenCalledTimes(1)
  expect(deps.clearAuthSession).toHaveBeenCalledTimes(1)
})

test("calls wx.login only through an explicit start and nowhere else", async () => {
  const deps = makeDeps({
    requestJson: jest.fn(() => Promise.resolve(REGISTRATION_REQUIRED_RESPONSE)),
  })
  await startWechatLogin(deps)
  expect(deps.invokeWxLogin).toHaveBeenCalledTimes(1)

  global.wx.login = jest.fn()
  await completeRegistration(
    {registrationToken: "reg-token-1", nickname: "Lin Qiao"},
    makeDeps({
      requestJson: jest.fn(() => Promise.resolve(AUTHENTICATED_RESPONSE)),
    }),
  )
  expect(global.wx.login).not.toHaveBeenCalled()
})

test("fails fast when WeChat denies the login code", async () => {
  const deps = makeDeps()
  deps.invokeWxLogin.mockImplementation((options) => {
    options.fail()
  })

  await expect(startWechatLogin(deps)).rejects.toEqual(
    new LoginError("wechat_login_failed"),
  )
  expect(requestCalls).toEqual([])
})

test("registers with a nickname over JSON and writes both caches", async () => {
  const deps = makeDeps({
    requestJson: jest.fn((options) => {
      requestCalls.push(options)
      return Promise.resolve(AUTHENTICATED_RESPONSE)
    }),
  })

  await expect(
    completeRegistration(
      {registrationToken: "reg-token-1", nickname: "  Lin Qiao  "},
      deps,
    ),
  ).resolves.toBeUndefined()

  expect(requestCalls[0]).toEqual({
    url: "http://127.0.0.1:8080/api/v1/auth/wechat/registrations",
    method: "POST",
    data: {registration_token: "reg-token-1", nickname: "Lin Qiao"},
  })
  expect(deps.writeAuthSession).toHaveBeenCalledTimes(1)
  expect(deps.writeCurrentUserSnapshot).toHaveBeenCalledTimes(1)
})

test("registers with an avatar over multipart without extra Authorization", async () => {
  const deps = makeDeps({
    uploadMultipart: jest.fn((options) => {
      uploadCalls.push(options)
      return Promise.resolve(AUTHENTICATED_RESPONSE)
    }),
  })

  await completeRegistration(
    {
      registrationToken: "reg-token-1",
      nickname: "Lin Qiao",
      avatarFilePath: "wxfile://tmp/avatar.png",
    },
    deps,
  )

  expect(deps.requestJson).not.toHaveBeenCalled()
  expect(uploadCalls[0]).toEqual({
    url: "http://127.0.0.1:8080/api/v1/auth/wechat/avatar-registrations",
    filePath: "wxfile://tmp/avatar.png",
    name: "file",
    formData: {registration_token: "reg-token-1", nickname: "Lin Qiao"},
  })
  expect(deps.writeAuthSession).toHaveBeenCalledTimes(1)
})

test("maps credential and storage failures to safe recoverable errors", async () => {
  const credentialDeps = makeDeps({
    requestJson: jest.fn(() =>
      Promise.reject(
        new TransportError("request_failed", 401, "registration_token_invalid"),
      ),
    ),
  })
  await expect(
    completeRegistration(
      {registrationToken: "stale", nickname: "Lin Qiao"},
      credentialDeps,
    ),
  ).rejects.toEqual(new LoginError("request_failed", "registration_token_invalid"))

  const storageDeps = makeDeps({
    requestJson: jest.fn(() =>
      Promise.reject(
        new TransportError("request_failed", 503, "storage_unavailable"),
      ),
    ),
  })
  await expect(
    completeRegistration(
      {registrationToken: "reg-token-1", nickname: "Lin Qiao"},
      storageDeps,
    ),
  ).rejects.toEqual(new LoginError("request_failed", "storage_unavailable"))

  const invalidDeps = makeDeps()
  await expect(
    completeRegistration(
      {registrationToken: "reg-token-1", nickname: "   "},
      invalidDeps,
    ),
  ).rejects.toEqual(new LoginError("request_failed", "invalid_nickname"))
  expect(invalidDeps.requestJson).not.toHaveBeenCalled()
})

test("validates the nickname locally with the same rules as the backend", () => {
  expect(validateLoginNickname("  Lin Qiao  ")).toBe("Lin Qiao")
  expect(validateLoginNickname("包小明")).toBe("包小明")
  expect(validateLoginNickname("   ")).toBeNull()
  expect(validateLoginNickname("a".repeat(201))).toBeNull()
  expect(validateLoginNickname("bad\u0007name")).toBeNull()
})
