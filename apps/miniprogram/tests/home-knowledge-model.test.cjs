const fs = require("node:fs")
const path = require("node:path")
const {
  HOME_KNOWLEDGE_FIXTURE,
} = require("../miniprogram/fixtures/home-knowledge.ts")
const {
  CURRENT_USER_CACHE_KEY,
  CURRENT_USER_CACHE_SCHEMA_VERSION,
  currentUserSnapshotFromOverview,
  readCurrentUserSnapshot,
  resetCurrentUserMemoryForTests,
  writeCurrentUserSnapshot,
} = require("../miniprogram/services/current-user-store.ts")
const {
  findHomeTopic,
  formatHomeHeader,
  formatLearningProgress,
  formatTopicSummary,
} = require("../miniprogram/utils/home-knowledge.ts")

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

test("keeps the deterministic home model complete and out of WXML", () => {
  expect(HOME_KNOWLEDGE_FIXTURE.learningCards).toHaveLength(3)
  expect(HOME_KNOWLEDGE_FIXTURE.topics.map((topic) => topic.name)).toEqual([
    "Agent 系统",
    "RAG",
    "Prompt 与上下文",
    "模型应用",
    "评测与可靠性",
    "工程化",
  ])
  expect(
    HOME_KNOWLEDGE_FIXTURE.topics.reduce(
      (total, topic) => total + topic.knowledgePointCount,
      0,
    ),
  ).toBe(48)

  const selected = findHomeTopic(
    HOME_KNOWLEDGE_FIXTURE.topics,
    HOME_KNOWLEDGE_FIXTURE.initialSelectedTopicId,
  )
  expect(formatTopicSummary(selected)).toBe("RAG · 12 个知识点")
  expect(formatLearningProgress(HOME_KNOWLEDGE_FIXTURE.learningCards[0])).toBe(
    "03 / 08",
  )

  const wxml = fs.readFileSync(
    path.resolve(
      __dirname,
      "../miniprogram/components/home-knowledge-overview/index.wxml",
    ),
    "utf8",
  )
  for (const value of [
    ...HOME_KNOWLEDGE_FIXTURE.topics.map((topic) => topic.name),
    ...HOME_KNOWLEDGE_FIXTURE.learningCards.map((card) => card.title),
  ]) {
    expect(wxml).not.toContain(value)
  }
})

test("formats the local date and all greeting boundaries deterministically", () => {
  for (const [hour, minute, greeting] of [
    [0, 0, "晚上好"],
    [5, 0, "早上好"],
    [12, 0, "下午好"],
    [18, 0, "晚上好"],
  ]) {
    expect(formatHomeHeader(new Date(2026, 8, 29, hour, minute))).toEqual({
      dateLabel: "2026.09.29 · 今日训练",
      greeting,
    })
  }
})

test("validates, normalizes, persists, and rejects obsolete user snapshots", () => {
  const snapshot = currentUserSnapshotFromOverview({
    id: " user-7 ",
    nickname: " Lin Qiao ",
    avatar_url: " https://example.invalid/lin.png ",
    default_target_profile: {
      id: "profile-7",
      target_role: "Platform Engineer",
      relevant_experience_months: 48,
    },
    current_resume: null,
    recent_scores: [],
  })
  expect(snapshot).toEqual({
    schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
    userId: "user-7",
    nickname: "Lin Qiao",
    avatarUrl: "https://example.invalid/lin.png",
  })

  writeCurrentUserSnapshot(snapshot)
  resetCurrentUserMemoryForTests()
  expect(readCurrentUserSnapshot()).toEqual(snapshot)

  storage.set(CURRENT_USER_CACHE_KEY, {
    schemaVersion: 0,
    userId: "previous-user",
    nickname: "Previous User",
  })
  resetCurrentUserMemoryForTests()
  expect(readCurrentUserSnapshot()).toBeNull()
  expect(wx.removeStorageSync).toHaveBeenCalledWith(CURRENT_USER_CACHE_KEY)
})
