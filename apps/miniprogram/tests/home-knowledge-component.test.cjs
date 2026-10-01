const path = require("node:path")
const simulate = require("miniprogram-simulate")
const {
  CURRENT_USER_CACHE_KEY,
  CURRENT_USER_CACHE_SCHEMA_VERSION,
  resetCurrentUserMemoryForTests,
  writeCurrentUserSnapshot,
} = require("../miniprogram/services/current-user-store.ts")
const {
  setHomeClockForTests,
} = require("../miniprogram/utils/home-knowledge.ts")

const componentPath = path.resolve(
  __dirname,
  "../miniprogram/components/home-knowledge-overview/index",
)
let componentId
let storage

const PROFILE_SNAPSHOT = {
  schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
  userId: "user-mira",
  nickname: "Mira Chen",
  avatarUrl: "https://example.invalid/mira.png",
  avatarUrlExpiresAt: "2099-01-01T00:00:00Z",
  defaultTargetProfile: {
    targetRole: "AI Platform Engineer",
    relevantExperienceMonths: 50,
  },
}

beforeAll(() => {
  componentId = simulate.load(componentPath, {compiler: "simulate"})
})

beforeEach(() => {
  document.body.innerHTML = ""
  storage = new Map()
  global.wx = {
    getStorageSync: jest.fn((key) => storage.get(key)),
    reLaunch: jest.fn(),
    removeStorageSync: jest.fn((key) => storage.delete(key)),
    request: jest.fn(),
    setStorageSync: jest.fn((key, value) => storage.set(key, value)),
    switchTab: jest.fn(),
  }
  resetCurrentUserMemoryForTests()
  setHomeClockForTests(() => new Date(2026, 8, 29, 5, 0))
})

afterEach(() => {
  setHomeClockForTests(null)
})

test("renders an immediate cache hit without any overview request", () => {
  writeCurrentUserSnapshot(PROFILE_SNAPSHOT)
  const component = renderComponent()

  expect(component.data.status).toBe("success")
  expect(component.dom.textContent).toContain("早上好，Mira Chen")
  expect(component.dom.textContent).toContain("2026.09.29 · 今日训练")
  expect(wx.request).not.toHaveBeenCalled()
  expect(wx.reLaunch).not.toHaveBeenCalled()
})

test("re-enters the login page when the cache is missing or corrupt", () => {
  const missingComponent = renderComponent()

  expect(missingComponent.data.status).toBe("loading")
  expect(missingComponent.dom.textContent).not.toContain("Mira Chen")
  expect(wx.request).not.toHaveBeenCalled()
  expect(wx.reLaunch).toHaveBeenCalledWith({url: "/pages/login/index"})

  document.body.innerHTML = ""
  wx.reLaunch.mockClear()
  storage.set(CURRENT_USER_CACHE_KEY, {
    schemaVersion: 0,
    userId: "old-user",
    nickname: "Stale Nickname",
  })
  resetCurrentUserMemoryForTests()
  const corruptComponent = renderComponent()

  expect(wx.removeStorageSync).toHaveBeenCalledWith(CURRENT_USER_CACHE_KEY)
  expect(corruptComponent.dom.textContent).not.toContain("Stale Nickname")
  expect(wx.request).not.toHaveBeenCalled()
  expect(wx.reLaunch).toHaveBeenCalledWith({url: "/pages/login/index"})
})

test("prompts an empty target profile and switches to the profile tab", async () => {
  writeCurrentUserSnapshot({
    ...PROFILE_SNAPSHOT,
    defaultTargetProfile: null,
  })
  const component = renderComponent()

  const text = component.dom.textContent
  expect(text).toContain("先设置你的目标岗位")
  expect(component.querySelector("#go-profile")).toBeDefined()

  component.querySelector("#go-profile").dispatchEvent("tap")
  await simulate.sleep(0)
  expect(wx.switchTab).toHaveBeenCalledWith({url: "/pages/profile/index"})
})

test("shows no profile hint once a target profile exists", () => {
  writeCurrentUserSnapshot(PROFILE_SNAPSHOT)
  const component = renderComponent()

  expect(component.dom.textContent).not.toContain("先设置你的目标岗位")
})

test("clears previous user content and re-enters login after invalidation", () => {
  writeCurrentUserSnapshot(PROFILE_SNAPSHOT)
  const component = renderComponent()
  expect(component.dom.textContent).toContain("Mira Chen")

  storage.clear()
  resetCurrentUserMemoryForTests()
  component.triggerPageLifeTime("show")
  expect(component.data.currentUser).toBeNull()
  expect(component.data.status).toBe("loading")
  expect(component.dom.textContent).not.toContain("Mira Chen")
  expect(wx.reLaunch).toHaveBeenCalledWith({url: "/pages/login/index"})
})

test("observes a profile saved from the profile tab on the next show", () => {
  writeCurrentUserSnapshot({
    ...PROFILE_SNAPSHOT,
    defaultTargetProfile: null,
  })
  const component = renderComponent()
  expect(component.dom.textContent).toContain("先设置你的目标岗位")

  writeCurrentUserSnapshot(PROFILE_SNAPSHOT)
  component.triggerPageLifeTime("show")

  expect(component.data.currentUser.defaultTargetProfile).toEqual({
    targetRole: "AI Platform Engineer",
    relevantExperienceMonths: 50,
  })
  expect(component.dom.textContent).not.toContain("先设置你的目标岗位")
})

test("keeps swipe, topic, and reserved actions local across page shows", async () => {
  writeCurrentUserSnapshot(PROFILE_SNAPSHOT)
  const component = renderComponent()
  await simulate.sleep(0)

  component.instance.onSelectTopic({
    currentTarget: {dataset: {topicId: "engineering"}},
  })
  component.instance.onSwiperChange({detail: {current: 1}})
  component.instance.handleAction({
    currentTarget: {dataset: {action: "continue-learning"}},
  })
  await simulate.sleep(0)

  expect(component.data.selectedTopicId).toBe("engineering")
  expect(component.data.selectedTopicSummary).toBe("工程化 · 5 个知识点")
  expect(component.data.currentLearningIndex).toBe(1)
  expect(component.data.currentLearningProgress).toBe("05 / 08")
  expect(component.querySelectorAll(".topic-card-selected")).toHaveLength(1)
  expect(component.data.lastAction).toBe("continue-learning")

  component.triggerPageLifeTime("show")
  await simulate.sleep(0)
  expect(component.data.lastAction).toBe("continue-learning")
  expect(component.data.selectedTopicId).toBe("engineering")
  expect(wx.request).not.toHaveBeenCalled()
  expect(wx.reLaunch).not.toHaveBeenCalled()
})

function renderComponent() {
  const component = simulate.render(componentId)
  component.attach(document.body)
  return component
}
