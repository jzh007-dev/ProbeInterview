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

const OVERVIEW = {
  id: "user-mira",
  nickname: "Mira Chen",
  avatar_url: "https://example.invalid/mira.png",
  default_target_profile: {
    id: "profile-mira",
    target_role: "AI Platform Engineer",
    relevant_experience_months: 50,
  },
  current_resume: null,
  recent_scores: [],
}

beforeAll(() => {
  componentId = simulate.load(componentPath, {compiler: "simulate"})
})

beforeEach(() => {
  document.body.innerHTML = ""
  storage = new Map()
  global.wx = {
    downloadFile: jest.fn(),
    getStorageSync: jest.fn((key) => storage.get(key)),
    navigateTo: jest.fn(),
    previewDocument: jest.fn(),
    removeStorageSync: jest.fn((key) => storage.delete(key)),
    request: jest.fn(),
    setStorageSync: jest.fn((key, value) => storage.set(key, value)),
    switchTab: jest.fn(),
    uploadFile: jest.fn(),
  }
  resetCurrentUserMemoryForTests()
  setHomeClockForTests(() => new Date(2026, 8, 29, 5, 0))
})

afterEach(() => {
  setHomeClockForTests(null)
})

test("renders an immediate cache hit without requesting the overview", () => {
  writeCurrentUserSnapshot({
    schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
    userId: "user-lin",
    nickname: "Lin Qiao",
  })
  const component = renderComponent()

  expect(component.data.status).toBe("success")
  expect(component.dom.textContent).toContain("早上好，Lin Qiao")
  expect(component.dom.textContent).toContain("2026.09.29 · 今日训练")
  expect(wx.request).not.toHaveBeenCalled()
})

test("uses an honest fallback for missing or invalid cache and refreshes it", async () => {
  let completeRequest
  wx.request.mockImplementation((options) => {
    completeRequest = () =>
      options.success({
        statusCode: 200,
        data: OVERVIEW,
      })
  })
  const missingComponent = renderComponent()

  expect(missingComponent.dom.textContent).toContain("正在准备今日训练")
  expect(missingComponent.dom.textContent).not.toContain("Bao")
  expect(missingComponent.dom.textContent).not.toContain("Mira Chen")

  completeRequest()
  await simulate.sleep(0)

  expect(missingComponent.dom.textContent).toContain("早上好，Mira Chen")
  expect(storage.get(CURRENT_USER_CACHE_KEY)).toMatchObject({
    userId: "user-mira",
    nickname: "Mira Chen",
  })

  document.body.innerHTML = ""
  storage.set(CURRENT_USER_CACHE_KEY, {
    schemaVersion: 0,
    userId: "old-user",
    nickname: "Stale Nickname",
  })
  resetCurrentUserMemoryForTests()
  wx.request.mockImplementation((options) => {
    completeRequest = () =>
      options.success({
        statusCode: 200,
        data: {...OVERVIEW, nickname: "Ada Zhou"},
      })
  })
  const invalidComponent = renderComponent()

  expect(invalidComponent.dom.textContent).toContain("正在准备今日训练")
  expect(invalidComponent.dom.textContent).not.toContain("Stale Nickname")
  expect(wx.removeStorageSync).toHaveBeenCalledWith(CURRENT_USER_CACHE_KEY)

  completeRequest()
  await simulate.sleep(0)
  expect(invalidComponent.dom.textContent).toContain("Ada Zhou")
})

test("recovers from request failure and refreshes time on page show", async () => {
  wx.request
    .mockImplementationOnce((options) => options.fail({errMsg: "request:fail"}))
    .mockImplementationOnce((options) =>
      options.success({statusCode: 200, data: OVERVIEW}),
    )
  let now = new Date(2026, 8, 29, 17, 59)
  setHomeClockForTests(() => now)
  const component = renderComponent()

  await simulate.sleep(0)
  expect(component.dom.textContent).toContain("首页身份信息加载失败")
  expect(component.dom.textContent).not.toContain("Mira Chen")

  component.querySelector("#retry-home").dispatchEvent("tap")
  await simulate.sleep(0)
  expect(component.dom.textContent).toContain("下午好，Mira Chen")
  expect(wx.request).toHaveBeenCalledTimes(2)

  now = new Date(2026, 8, 30, 0, 0)
  component.triggerPageLifeTime("show")
  await simulate.sleep(0)
  expect(component.dom.textContent).toContain("2026.09.30 · 今日训练")
  expect(component.dom.textContent).toContain("晚上好，Mira Chen")
  expect(wx.request).toHaveBeenCalledTimes(2)
})

test("renders the complete overview and keeps swipe, topic, and reserved actions local", async () => {
  wx.request.mockImplementation((options) => {
    options.success({statusCode: 200, data: OVERVIEW})
  })
  const component = renderComponent()
  await simulate.sleep(0)

  const text = component.dom.textContent
  for (const value of [
    "本周训练覆盖",
    "待复盘 4",
    "RAG 评测不能只看答案正确率",
    "工具调用必须服从权限与状态边界",
    "上下文预算需要围绕任务证据分配",
    "Agent 系统",
    "RAG",
    "Prompt 与上下文",
    "模型应用",
    "评测与可靠性",
    "工程化",
  ]) {
    expect(text).toContain(value)
  }
  expect(component.data.selectedTopicSummary).toBe("RAG · 12 个知识点")
  expect(component.querySelectorAll(".topic-card")).toHaveLength(6)
  expect(component.querySelectorAll(".topic-card-selected")).toHaveLength(1)
  expect(component.querySelectorAll(".swiper-indicator-active")).toHaveLength(1)

  wx.navigateTo.mockClear()
  wx.switchTab.mockClear()
  wx.previewDocument.mockClear()
  wx.uploadFile.mockClear()
  wx.downloadFile.mockClear()
  wx.setStorageSync.mockClear()

  component.instance.onSelectTopic({
    currentTarget: {dataset: {topicId: "engineering"}},
  })
  component.instance.onSwiperChange({detail: {current: 1}})
  component.instance.handleAction({
    currentTarget: {dataset: {action: "search-knowledge"}},
  })
  component.instance.handleAction({
    currentTarget: {dataset: {action: "continue-learning"}},
  })
  await simulate.sleep(0)

  expect(component.data.selectedTopicId).toBe("engineering")
  expect(component.data.selectedTopicSummary).toBe("工程化 · 5 个知识点")
  expect(component.data.currentLearningIndex).toBe(1)
  expect(component.data.currentLearningProgress).toBe("05 / 08")
  expect(component.querySelectorAll(".topic-card-selected")).toHaveLength(1)
  expect(component.querySelectorAll(".swiper-indicator-active")).toHaveLength(1)
  expect(component.data.lastAction).toBe("continue-learning")
  expect(wx.request).toHaveBeenCalledTimes(1)
  expect(wx.navigateTo).not.toHaveBeenCalled()
  expect(wx.switchTab).not.toHaveBeenCalled()
  expect(wx.previewDocument).not.toHaveBeenCalled()
  expect(wx.uploadFile).not.toHaveBeenCalled()
  expect(wx.downloadFile).not.toHaveBeenCalled()
  expect(wx.setStorageSync).not.toHaveBeenCalled()
})

function renderComponent() {
  const component = simulate.render(componentId)
  component.attach(document.body)
  return component
}
