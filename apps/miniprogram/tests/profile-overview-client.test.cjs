const {
  AUTH_SESSION_CACHE_KEY,
  AUTH_SESSION_CACHE_SCHEMA_VERSION,
  resetAuthSessionMemoryForTests,
} = require("../miniprogram/services/auth-store.ts")
const {
  describeProfileError,
  fetchProfileOverview,
  putDefaultTargetProfile,
} = require("../miniprogram/services/profile-overview.ts")
const {TransportError} = require("../miniprogram/services/transport.ts")
const {
  parseExperienceMonthsInput,
  parseProfileOverview,
  parseTargetProfileResource,
  validateTargetRoleInput,
} = require("../miniprogram/utils/profile-overview.ts")
const {
  avatarInitials,
  formatExperience,
} = require("../miniprogram/utils/profile-overview.ts")

const SESSION = {
  schemaVersion: AUTH_SESSION_CACHE_SCHEMA_VERSION,
  accessToken: "token-profile",
  expiresAt: "2099-01-01T00:00:00Z",
}

const OVERVIEW = {
  id: "user-1",
  nickname: "Lin Qiao",
  avatar_url: "https://example.invalid/lin.png",
  avatar_url_expires_at: "2099-01-01T00:00:00Z",
  default_target_profile: {
    id: "profile-1",
    target_role: "Platform Engineer",
    relevant_experience_months: 27,
  },
  current_resume: null,
  recent_scores: [],
}

let storage

function okRequest(response, statusCode = 200) {
  return jest.fn((options) => {
    options.success({statusCode, data: response})
  })
}

beforeEach(() => {
  storage = new Map()
  global.wx = {
    getStorageSync: jest.fn((key) => storage.get(key)),
    reLaunch: jest.fn(),
    removeStorageSync: jest.fn((key) => storage.delete(key)),
    request: jest.fn(),
    setStorageSync: jest.fn((key, value) => storage.set(key, value)),
    uploadFile: jest.fn(),
  }
  resetAuthSessionMemoryForTests()
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
})

test("fetches the overview with the bearer token and validates the payload", async () => {
  const request = okRequest(OVERVIEW)
  global.wx.request = request

  await expect(fetchProfileOverview()).resolves.toEqual(OVERVIEW)

  const sent = request.mock.calls[0][0]
  expect(sent.url).toBe("http://127.0.0.1:8080/api/v1/me/overview")
  expect(sent.method).toBe("GET")
  expect(sent.header).toEqual({Authorization: "Bearer token-profile"})

  expect(parseProfileOverview({...OVERVIEW, nickname: "  "})).toBeNull()
  expect(
    parseProfileOverview({
      ...OVERVIEW,
      avatar_url: "https://example.invalid/lin.png",
      avatar_url_expires_at: null,
    }),
  ).toBeNull()
  expect(parseProfileOverview({...OVERVIEW, recent_scores: "nope"})).toBeNull()
})

test("rejects sanitized failures for the overview request", async () => {
  const problemRequest = jest.fn((options) => {
    options.success({
      statusCode: 503,
      data: {detail: "private upstream detail"},
    })
  })
  global.wx.request = problemRequest
  await expect(fetchProfileOverview()).rejects.toEqual(
    new TransportError("request_failed", 503, null),
  )

  const invalidRequest = okRequest({unexpected: true})
  global.wx.request = invalidRequest
  await expect(fetchProfileOverview()).rejects.toEqual(
    new TransportError("invalid_response"),
  )

  const failingRequest = jest.fn((options) => {
    options.fail({errMsg: "request:fail secret"})
  })
  global.wx.request = failingRequest
  await expect(fetchProfileOverview()).rejects.toEqual(
    new TransportError("network_error"),
  )

  expect(problemRequest).toHaveBeenCalled()
  expect(invalidRequest).toHaveBeenCalled()
  expect(failingRequest).toHaveBeenCalled()
})

test("saves the default target profile with the typed write contract", async () => {
  const saved = {
    id: "profile-9",
    target_role: "算法工程师",
    relevant_experience_months: 36,
  }
  const request = okRequest(saved, 200)
  global.wx.request = request

  await expect(
    putDefaultTargetProfile({targetRole: "算法工程师", relevantExperienceMonths: 36}),
  ).resolves.toEqual(saved)

  const sent = request.mock.calls[0][0]
  expect(sent.url).toBe("http://127.0.0.1:8080/api/v1/me/default-target-profile")
  expect(sent.method).toBe("PUT")
  expect(sent.data).toEqual({
    target_role: "算法工程师",
    relevant_experience_months: 36,
  })
  expect(sent.header).toEqual({Authorization: "Bearer token-profile"})

  expect(parseTargetProfileResource({id: "p", target_role: "r"})).toBeNull()
  expect(
    parseTargetProfileResource({
      id: "p",
      target_role: "r",
      relevant_experience_months: -1,
    }),
  ).toBeNull()
})

test("maps profile failures to safe messages", () => {
  expect(
    describeProfileError(new TransportError("request_failed", 422, "invalid_target_role")),
  ).toBe("目标岗位需为 1 到 200 个字符")
  expect(
    describeProfileError(new TransportError("request_failed", 422, "validation_error")),
  ).toBe("请检查目标岗位与经验月数的取值")
  expect(
    describeProfileError(new TransportError("request_failed", 422, "opaque_code")),
  ).toBe("请求失败，请稍后重试")
  expect(describeProfileError(new TransportError("network_error"))).toBe(
    "网络连接失败，请稍后重试",
  )
  expect(describeProfileError(new Error("raw"))).toBe("请求失败，请稍后重试")
})

test("validates target role and experience months inputs", () => {
  expect(validateTargetRoleInput("  AI 全栈开发 ")).toBe("AI 全栈开发")
  expect(validateTargetRoleInput("   ")).toBeNull()
  expect(validateTargetRoleInput("x".repeat(201))).toBeNull()
  expect(validateTargetRoleInput("角色\x1b")).toBeNull()

  expect(parseExperienceMonthsInput(" 36 ")).toBe(36)
  expect(parseExperienceMonthsInput("0")).toBe(0)
  expect(parseExperienceMonthsInput("600")).toBe(600)
  expect(parseExperienceMonthsInput("601")).toBeNull()
  expect(parseExperienceMonthsInput("-1")).toBeNull()
  expect(parseExperienceMonthsInput("3.5")).toBeNull()
  expect(parseExperienceMonthsInput("abc")).toBeNull()
})

test("formats experience and derives avatar initials from response values", () => {
  for (const [months, expected] of [
    [0, "0 个月"],
    [8, "8 个月"],
    [24, "2 年"],
    [27, "2 年 3 个月"],
  ]) {
    expect(formatExperience(months)).toBe(expected)
  }
  for (const [nickname, expected] of [
    ["Lin Qiao", "LQ"],
    ["包小明", "包小"],
    ["  ada   lovelace  ", "AL"],
    ["", "?"],
  ]) {
    expect(avatarInitials(nickname)).toBe(expected)
  }
})
