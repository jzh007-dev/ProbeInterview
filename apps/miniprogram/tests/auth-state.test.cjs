const {
  AUTH_SESSION_CACHE_KEY,
  AUTH_SESSION_CACHE_SCHEMA_VERSION,
} = require("../miniprogram/services/auth-store.ts")
const {
  CURRENT_USER_CACHE_KEY,
  CURRENT_USER_CACHE_SCHEMA_VERSION,
} = require("../miniprogram/services/current-user-store.ts")
const {
  clearAuthState,
  readValidSessionPair,
} = require("../miniprogram/services/auth-state.ts")
const {
  resetAuthSessionMemoryForTests,
} = require("../miniprogram/services/auth-store.ts")
const {
  resetCurrentUserMemoryForTests,
} = require("../miniprogram/services/current-user-store.ts")

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

beforeEach(() => {
  storage = new Map()
  global.wx = {
    getStorageSync: jest.fn((key) => storage.get(key)),
    removeStorageSync: jest.fn((key) => storage.delete(key)),
    setStorageSync: jest.fn((key, value) => storage.set(key, value)),
  }
  resetAuthSessionMemoryForTests()
  resetCurrentUserMemoryForTests()
})

test("returns a session pair only when both caches are valid together", () => {
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
  expect(readValidSessionPair()).toBeNull()

  storage.set(CURRENT_USER_CACHE_KEY, SNAPSHOT)
  expect(readValidSessionPair()).toEqual({session: SESSION, currentUser: SNAPSHOT})

  storage.set(AUTH_SESSION_CACHE_KEY, {
    ...SESSION,
    expiresAt: "2020-01-01T00:00:00Z",
  })
  resetAuthSessionMemoryForTests()
  expect(readValidSessionPair()).toBeNull()
})

test("starts no silent login when validating the session pair", () => {
  global.wx.login = jest.fn()
  expect(readValidSessionPair()).toBeNull()
  expect(global.wx.login).not.toHaveBeenCalled()
})

test("clears both the token cache and the display cache with one call", () => {
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
  storage.set(CURRENT_USER_CACHE_KEY, SNAPSHOT)

  clearAuthState()

  expect(storage.has(AUTH_SESSION_CACHE_KEY)).toBe(false)
  expect(storage.has(CURRENT_USER_CACHE_KEY)).toBe(false)
  expect(readValidSessionPair()).toBeNull()
})
