const {
  AUTH_SESSION_CACHE_KEY,
  AUTH_SESSION_CACHE_SCHEMA_VERSION,
  clearAuthSession,
  readAuthSession,
  resetAuthSessionMemoryForTests,
  writeAuthSession,
} = require("../miniprogram/services/auth-store.ts")

const SESSION = {
  schemaVersion: AUTH_SESSION_CACHE_SCHEMA_VERSION,
  accessToken: "token-abc",
  expiresAt: "2027-01-01T00:00:00Z",
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
})

test("round-trips a session between memory and device storage", () => {
  writeAuthSession(SESSION)
  expect(storage.get(AUTH_SESSION_CACHE_KEY)).toEqual(SESSION)

  resetAuthSessionMemoryForTests()
  expect(readAuthSession(new Date("2026-10-01T00:00:00Z"))).toEqual(SESSION)
})

test("drops an expired session and removes its stored entry", () => {
  writeAuthSession(SESSION)
  resetAuthSessionMemoryForTests()

  expect(readAuthSession(new Date("2027-01-01T00:00:00Z"))).toBeNull()
  expect(storage.has(AUTH_SESSION_CACHE_KEY)).toBe(false)
  expect(readAuthSession(new Date("2026-10-01T00:00:00Z"))).toBeNull()
})

test("treats missing entries as absent without touching storage", () => {
  for (const entry of [undefined, null, ""]) {
    storage.set(AUTH_SESSION_CACHE_KEY, entry)
    resetAuthSessionMemoryForTests()
    expect(readAuthSession()).toBeNull()
    expect(wx.removeStorageSync).not.toHaveBeenCalled()
  }
})

test("treats obsolete, damaged, and malformed entries as corrupt storage", () => {
  const corruptEntries = [
    {schemaVersion: 0, accessToken: "t", expiresAt: SESSION.expiresAt},
    {schemaVersion: 1, accessToken: "   ", expiresAt: SESSION.expiresAt},
    {schemaVersion: 1, accessToken: "t", expiresAt: "not-a-date"},
    {schemaVersion: 1, accessToken: "t", expiresAt: 12345},
    "garbage",
  ]

  for (const entry of corruptEntries) {
    storage.set(AUTH_SESSION_CACHE_KEY, entry)
    resetAuthSessionMemoryForTests()
    expect(readAuthSession()).toBeNull()
    expect(wx.removeStorageSync).toHaveBeenCalledWith(AUTH_SESSION_CACHE_KEY)
  }
})

test("rejects invalid writes without touching storage", () => {
  const invalidSessions = [
    {schemaVersion: 1, accessToken: "", expiresAt: SESSION.expiresAt},
    {schemaVersion: 1, accessToken: "t", expiresAt: "yesterday"},
    {schemaVersion: 2, accessToken: "t", expiresAt: SESSION.expiresAt},
  ]

  for (const session of invalidSessions) {
    expect(() => writeAuthSession(session)).toThrow()
  }
  expect(storage.size).toBe(0)
})

test("normalizes whitespace on write and clears both memory and storage", () => {
  writeAuthSession({...SESSION, accessToken: "  token-abc  "})
  expect(storage.get(AUTH_SESSION_CACHE_KEY).accessToken).toBe("token-abc")

  clearAuthSession()
  expect(storage.has(AUTH_SESSION_CACHE_KEY)).toBe(false)
  resetAuthSessionMemoryForTests()
  expect(readAuthSession()).toBeNull()
})
