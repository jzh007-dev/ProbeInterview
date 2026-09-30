const {
  CURRENT_USER_CACHE_KEY,
  CURRENT_USER_CACHE_SCHEMA_VERSION,
  clearCurrentUserSnapshot,
  currentUserSnapshotFromResource,
  readCurrentUserSnapshot,
  resetCurrentUserMemoryForTests,
  writeCurrentUserSnapshot,
} = require("../miniprogram/services/current-user-store.ts")

const RESOURCE = {
  id: "user-9",
  nickname: "Lin Qiao",
  avatar_url: "https://example.invalid/lin.png",
  avatar_url_expires_at: "2099-01-01T00:00:00Z",
  default_target_profile: {
    target_role: "Platform Engineer",
    relevant_experience_months: 27,
  },
}

const SNAPSHOT = {
  schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
  userId: "user-9",
  nickname: "Lin Qiao",
  avatarUrl: "https://example.invalid/lin.png",
  avatarUrlExpiresAt: "2099-01-01T00:00:00Z",
  defaultTargetProfile: {
    targetRole: "Platform Engineer",
    relevantExperienceMonths: 27,
  },
}

let storage

beforeEach(() => {
  storage = new Map()
  global.wx = {
    getStorageSync: jest.fn((key) => storage.get(key)),
    removeStorageSync: jest.fn((key) => storage.delete(key)),
    setStorageSync: jest.fn((key, value) => storage.set(key, value)),
  }
  resetCurrentUserMemoryForTests()
})

test("round-trips nullable avatar and profile summaries in both caches", () => {
  expect(currentUserSnapshotFromResource(RESOURCE)).toEqual(SNAPSHOT)

  const bare = currentUserSnapshotFromResource({
    ...RESOURCE,
    avatar_url: null,
    avatar_url_expires_at: null,
    default_target_profile: null,
  })
  expect(bare).toEqual({
    schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
    userId: "user-9",
    nickname: "Lin Qiao",
    avatarUrl: null,
    avatarUrlExpiresAt: null,
    defaultTargetProfile: null,
  })

  writeCurrentUserSnapshot(bare)
  resetCurrentUserMemoryForTests()
  expect(readCurrentUserSnapshot()).toEqual(bare)

  writeCurrentUserSnapshot(SNAPSHOT)
  resetCurrentUserMemoryForTests()
  expect(readCurrentUserSnapshot()).toEqual(SNAPSHOT)
  expect(storage.get(CURRENT_USER_CACHE_KEY)).toEqual(SNAPSHOT)
})

test("hides only the expired avatar while keeping the rest of the snapshot", () => {
  const expiring = {
    ...SNAPSHOT,
    avatarUrlExpiresAt: "2026-09-30T12:00:00Z",
  }
  writeCurrentUserSnapshot(expiring)
  resetCurrentUserMemoryForTests()

  expect(
    readCurrentUserSnapshot(new Date("2026-09-30T11:59:59Z")),
  ).toEqual(expiring)
  expect(readCurrentUserSnapshot(new Date("2026-09-30T12:00:00Z"))).toEqual({
    ...expiring,
    avatarUrl: null,
    avatarUrlExpiresAt: null,
  })
})

test("treats missing entries as absent without touching storage", () => {
  for (const entry of [undefined, null, ""]) {
    storage.set(CURRENT_USER_CACHE_KEY, entry)
    resetCurrentUserMemoryForTests()
    expect(readCurrentUserSnapshot()).toBeNull()
    expect(wx.removeStorageSync).not.toHaveBeenCalled()
  }
})

test("treats obsolete versions and damaged entries as corrupt storage", () => {
  const corruptEntries = [
    {...SNAPSHOT, schemaVersion: 1},
    {...SNAPSHOT, userId: "   "},
    {...SNAPSHOT, avatarUrl: "https://example.invalid/x.png", avatarUrlExpiresAt: null},
    {...SNAPSHOT, defaultTargetProfile: {targetRole: "", relevantExperienceMonths: 1}},
    {...SNAPSHOT, defaultTargetProfile: {targetRole: "Role", relevantExperienceMonths: 1.5}},
    "not-an-object",
  ]

  for (const entry of corruptEntries) {
    storage.set(CURRENT_USER_CACHE_KEY, entry)
    resetCurrentUserMemoryForTests()
    expect(readCurrentUserSnapshot()).toBeNull()
    expect(wx.removeStorageSync).toHaveBeenCalledWith(CURRENT_USER_CACHE_KEY)
  }
})

test("rejects resources that break the display contract", () => {
  const invalidResources = [
    {...RESOURCE, id: "  "},
    {...RESOURCE, nickname: ""},
    {...RESOURCE, avatar_url: "https://example.invalid/x.png", avatar_url_expires_at: null},
    {...RESOURCE, avatar_url: null, avatar_url_expires_at: "2099-01-01T00:00:00Z"},
    {...RESOURCE, default_target_profile: {target_role: "  ", relevant_experience_months: 1}},
  ]

  for (const resource of invalidResources) {
    expect(() => currentUserSnapshotFromResource(resource)).toThrow()
  }
  expect(storage.size).toBe(0)
})

test("clears both memory and storage with one call", () => {
  writeCurrentUserSnapshot(SNAPSHOT)

  clearCurrentUserSnapshot()
  expect(storage.has(CURRENT_USER_CACHE_KEY)).toBe(false)
  expect(readCurrentUserSnapshot()).toBeNull()
})
