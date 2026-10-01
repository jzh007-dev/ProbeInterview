const path = require("node:path")
const simulate = require("miniprogram-simulate")
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
const {resetTransportInvalidationForTests} = require("../miniprogram/services/transport.ts")

const componentPath = path.resolve(
  __dirname,
  "../miniprogram/components/profile-overview/index",
)
let componentId
let storage

const SESSION = {
  schemaVersion: AUTH_SESSION_CACHE_SCHEMA_VERSION,
  accessToken: "token-profile",
  expiresAt: "2099-01-01T00:00:00Z",
}

const OVERVIEW = {
  id: "user-2",
  nickname: "Lin Qiao",
  avatar_url: "https://example.invalid/lin.png",
  avatar_url_expires_at: "2099-01-01T00:00:00Z",
  default_target_profile: {
    id: "profile-2",
    target_role: "Platform Engineer",
    relevant_experience_months: 27,
  },
  current_resume: {
    id: "resume-2",
    original_file_name: "lin-profile.pdf",
    media_type: "application/pdf",
    size_bytes: 2048,
    revision: 2,
    uploaded_at: "2026-09-29T08:00:00Z",
    updated_at: "2026-09-29T08:05:00Z",
  },
  recent_scores: [],
}

const OVERVIEW_WITHOUT_RESUME = {...OVERVIEW, current_resume: null}

function cachedSnapshot(overrides = {}) {
  return {
    schemaVersion: CURRENT_USER_CACHE_SCHEMA_VERSION,
    userId: "user-2",
    nickname: "Lin Qiao",
    avatarUrl: null,
    avatarUrlExpiresAt: null,
    defaultTargetProfile: null,
    ...overrides,
  }
}

beforeEach(() => {
  document.body.innerHTML = ""
  storage = new Map()
  global.wx = {
    getStorageSync: jest.fn((key) => storage.get(key)),
    navigateTo: jest.fn(),
    reLaunch: jest.fn(),
    removeStorageSync: jest.fn((key) => storage.delete(key)),
    request: jest.fn(),
    setStorageSync: jest.fn((key, value) => storage.set(key, value)),
    switchTab: jest.fn(),
    uploadFile: jest.fn(),
  }
  resetAuthSessionMemoryForTests()
  resetCurrentUserMemoryForTests()
  resetTransportInvalidationForTests()
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
})

beforeAll(() => {
  componentId = simulate.load(componentPath, {compiler: "simulate"})
})

test("renders cached read-only identity and refreshes from the overview", async () => {
  writeCache(cachedSnapshot())
  wx.request.mockImplementation((options) => {
    options.success({statusCode: 200, data: OVERVIEW})
  })
  const component = renderComponent()

  expect(component.dom.textContent).toContain("Lin Qiao")
  expect(component.dom.textContent).toContain("尚未设置目标岗位")
  expect(component.instance.data.viewer.nickname).toBe("Lin Qiao")

  await simulate.sleep(0)

  expect(component.dom.textContent).toContain("Platform Engineer")
  expect(component.dom.textContent).toContain("2 年 3 个月")
  expect(component.dom.textContent).toContain("lin-profile.pdf")
  expect(storage.get(CURRENT_USER_CACHE_KEY)).toMatchObject({
    nickname: "Lin Qiao",
    avatarUrl: "https://example.invalid/lin.png",
    defaultTargetProfile: {
      targetRole: "Platform Engineer",
      relevantExperienceMonths: 27,
    },
  })

  component.querySelector(".avatar-image").dispatchEvent("error")
  await simulate.sleep(0)
  expect(component.dom.textContent).toContain("LQ")
})

test("creates a target profile through pickers and collapses the form on success", async () => {
  writeCache(cachedSnapshot())
  wx.request
    .mockImplementationOnce((options) => {
      options.success({statusCode: 200, data: OVERVIEW_WITHOUT_RESUME})
    })
    .mockImplementationOnce((options) => {
      expect(options.method).toBe("PUT")
      expect(options.url).toBe(
        "http://127.0.0.1:8080/api/v1/me/default-target-profile",
      )
      options.success({
        statusCode: 200,
        data: {
          id: "profile-9",
          target_role: "AI 全栈开发",
          relevant_experience_months: 36,
        },
      })
    })
  const component = renderComponent()
  await simulate.sleep(0)

  // The form stays collapsed until the user opens it.
  expect(component.querySelector("#save-target-profile")).toBeUndefined()
  component.querySelector("#edit-target-profile").dispatchEvent("tap")
  await simulate.sleep(0)
  expect(component.querySelector("#save-target-profile")).toBeDefined()

  component.querySelector("#target-role-picker").dispatchEvent("change", {
    detail: {value: 0},
  })
  component.querySelector("#target-years-picker").dispatchEvent("change", {
    detail: {value: 2},
  })
  component.querySelector("#save-target-profile").dispatchEvent("tap")
  await simulate.sleep(0)

  expect(component.dom.textContent).toContain("目标画像已保存")
  expect(component.dom.textContent).toContain("3 年")
  // Bug 2: the submit button disappears once the profile is saved.
  expect(component.querySelector("#save-target-profile")).toBeUndefined()
  expect(component.dom.textContent).toContain("修改目标画像")
  expect(storage.get(CURRENT_USER_CACHE_KEY)).toMatchObject({
    defaultTargetProfile: {
      targetRole: "AI 全栈开发",
      relevantExperienceMonths: 36,
    },
  })
  expect(wx.request).toHaveBeenCalledTimes(2)
})

test("keeps the open form and the old cache when the save fails", async () => {
  writeCache(cachedSnapshot())
  wx.request
    .mockImplementationOnce((options) => {
      options.success({statusCode: 200, data: OVERVIEW_WITHOUT_RESUME})
    })
    .mockImplementationOnce((options) => {
      options.success({
        statusCode: 422,
        data: {code: "invalid_target_role", detail: "private upstream detail"},
      })
    })
  const component = renderComponent()
  await simulate.sleep(0)

  component.querySelector("#edit-target-profile").dispatchEvent("tap")
  await simulate.sleep(0)
  component.querySelector("#target-years-picker").dispatchEvent("change", {
    detail: {value: 4},
  })
  component.querySelector("#save-target-profile").dispatchEvent("tap")
  await simulate.sleep(0)

  expect(component.dom.textContent).toContain("目标岗位需为 1 到 200 个字符")
  expect(component.dom.textContent).not.toContain("目标画像已保存")
  // The form stays open with the selections intact for a retry.
  expect(component.querySelector("#save-target-profile")).toBeDefined()
  expect(component.instance.data.profileYearsIndex).toBe(4)
  // The refresh from the overview brought the previous server-truth profile;
  // a failed save must leave exactly that cache untouched.
  expect(storage.get(CURRENT_USER_CACHE_KEY)).toMatchObject({
    defaultTargetProfile: {
      targetRole: "Platform Engineer",
      relevantExperienceMonths: 27,
    },
  })
})

test("seeds the years picker from the saved profile in years", async () => {
  writeCache(
    cachedSnapshot({
      defaultTargetProfile: {
        targetRole: "AI 全栈开发",
        relevantExperienceMonths: 36,
      },
    }),
  )
  wx.request.mockImplementation((options) => {
    options.success({statusCode: 200, data: OVERVIEW})
  })
  const component = renderComponent()
  await simulate.sleep(0)

  // Server truth wins over the stale cache summary after the refresh.
  expect(component.dom.textContent).toContain("目标岗位")
  expect(component.dom.textContent).toContain("2 年 3 个月")
  component.querySelector("#edit-target-profile").dispatchEvent("tap")
  await simulate.sleep(0)
  // 27 months has no exact year match; the picker falls back to 1 年.
  expect(component.instance.data.profileYearsIndex).toBe(0)
  expect(component.instance.data.targetRoleOptions).toContain("AI 全栈开发")
})

test("invalidation clears both caches and re-enters the login page", async () => {
  writeCache(cachedSnapshot())
  wx.request.mockImplementation((options) => {
    options.success({statusCode: 401, data: {code: "authentication_required"}})
  })
  const component = renderComponent()

  expect(component.dom.textContent).toContain("Lin Qiao")
  await simulate.sleep(0)

  expect(wx.reLaunch).toHaveBeenCalledWith({url: "/pages/login/index"})
  expect(storage.has(AUTH_SESSION_CACHE_KEY)).toBe(false)
  expect(storage.has(CURRENT_USER_CACHE_KEY)).toBe(false)
})

test("recovers from a failed overview load through the retry action", async () => {
  wx.request
    .mockImplementationOnce((options) => options.fail({errMsg: "request:fail"}))
    .mockImplementationOnce((options) => {
      options.success({statusCode: 200, data: OVERVIEW_WITHOUT_RESUME})
    })
  const component = renderComponent()

  await simulate.sleep(0)
  expect(component.dom.textContent).toContain("个人概览加载失败")

  component.querySelector("#retry-overview").dispatchEvent("tap")
  await simulate.sleep(0)

  expect(wx.request).toHaveBeenCalledTimes(2)
  const text = component.dom.textContent
  expect(text).toContain("Lin Qiao")
  expect(text).toContain("尚未上传，将在模拟面试时添加")
  expect(text).toContain("暂无面试记录")
  expect(component.querySelector("#preview-current-resume")).toBeUndefined()
})

test("recognizes reserved actions without navigation or file calls", async () => {
  writeCache(cachedSnapshot())
  wx.request.mockImplementation((options) => {
    options.success({statusCode: 200, data: OVERVIEW})
  })
  const component = renderComponent()
  await simulate.sleep(0)

  const actions = [
    "open-settings",
    "preview-current-resume",
    "open-score-history",
    "configure-interview-language",
    "open-privacy-data",
    "open-about",
  ]
  for (const action of actions) {
    component.instance.handleAction({currentTarget: {dataset: {action}}})
    expect(component.instance.data.lastAction).toBe(action)
  }

  expect(wx.navigateTo).not.toHaveBeenCalled()
  expect(wx.switchTab).not.toHaveBeenCalled()
  expect(wx.uploadFile).not.toHaveBeenCalled()
  expect(wx.request).toHaveBeenCalledTimes(1)
})

function renderComponent() {
  const component = simulate.render(componentId)
  component.attach(document.body)
  return component
}

function writeCache(snapshot) {
  storage.set(CURRENT_USER_CACHE_KEY, snapshot)
}
