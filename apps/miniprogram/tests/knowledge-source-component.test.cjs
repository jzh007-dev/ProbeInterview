const path = require("node:path")
const simulate = require("miniprogram-simulate")
const {
  AUTH_SESSION_CACHE_KEY,
  AUTH_SESSION_CACHE_SCHEMA_VERSION,
  resetAuthSessionMemoryForTests,
} = require("../miniprogram/services/auth-store.ts")
const {
  CURRENT_USER_CACHE_KEY,
  resetCurrentUserMemoryForTests,
} = require("../miniprogram/services/current-user-store.ts")
const {resetTransportInvalidationForTests} = require("../miniprogram/services/transport.ts")

const componentPath = path.resolve(
  __dirname,
  "../miniprogram/components/knowledge-source-manager/index",
)
let componentId

const SESSION = {
  schemaVersion: AUTH_SESSION_CACHE_SCHEMA_VERSION,
  accessToken: "token-upload",
  expiresAt: "2099-01-01T00:00:00Z",
}
const SNAPSHOT = {
  schemaVersion: 2,
  userId: "user-upload",
  nickname: "Owner",
  avatarUrl: null,
  avatarUrlExpiresAt: null,
  defaultTargetProfile: null,
}

const EMPTY_COLLECTION = {
  quota: {
    timezone: "Asia/Shanghai",
    daily_limit: 2,
    daily_used: 0,
    effective_source_limit: 100,
    effective_source_count: 0,
  },
  items: [],
}
const PRIVATE_SOURCE = {
  id: "source-private",
  original_filename: "private.md",
  scope: "PRIVATE",
  processing_status: "PENDING_EXTRACTION",
  uploaded_at: "2026-09-30T05:00:00Z",
}
const PUBLIC_SOURCE = {
  id: "source-public",
  original_filename: "public.md",
  scope: "PUBLIC",
  processing_status: "PENDING_EXTRACTION",
  uploaded_at: "2026-09-30T06:00:00Z",
}
const LONG_PRIVATE_SOURCE = {
  ...PRIVATE_SOURCE,
  id: "source-long-private",
  original_filename:
    "jdOpkWRtVw4r47e7f186c8827887b7342a81caaa2be4.md",
}

beforeAll(() => {
  componentId = simulate.load(componentPath, {compiler: "simulate"})
})

beforeEach(() => {
  document.body.innerHTML = ""
  jest.spyOn(Date, "now").mockReturnValue(1790748000000)
  jest.spyOn(Math, "random").mockReturnValue(0.123456789)
  const storage = new Map()
  global.wx = {
    chooseMessageFile: jest.fn(),
    getStorageSync: (key) => storage.get(key),
    reLaunch: jest.fn(),
    removeStorageSync: (key) => storage.delete(key),
    request: jest.fn(),
    setStorageSync: (key, value) => storage.set(key, value),
    uploadFile: jest.fn(),
  }
  resetAuthSessionMemoryForTests()
  resetCurrentUserMemoryForTests()
  resetTransportInvalidationForTests()
  storage.set(AUTH_SESSION_CACHE_KEY, SESSION)
  storage.set(CURRENT_USER_CACHE_KEY, SNAPSHOT)
})

afterEach(() => {
  jest.restoreAllMocks()
})

test("renders loading then an honest empty state with real quota", async () => {
  let finishList
  wx.request.mockImplementation((options) => {
    finishList = () => options.success({statusCode: 200, data: EMPTY_COLLECTION})
  })
  const component = renderComponent()

  expect(component.dom.textContent).toContain("正在加载知识资料")
  expect(component.dom.textContent).not.toContain("已完成")
  await simulate.sleep(0)
  finishList()
  await simulate.sleep(0)

  const text = component.dom.textContent
  expect(text).toContain("还没有知识资料")
  expect(text).toContain("今日 0 / 2")
  expect(text).not.toContain("私人题库")
  expect(text).not.toContain("知识节点")
})

test("selects one Markdown file, shows size, and defaults scope to private", async () => {
  wx.request.mockImplementation((options) =>
    options.success({statusCode: 200, data: EMPTY_COLLECTION}),
  )
  wx.chooseMessageFile.mockImplementation((options) =>
    options.success({
      tempFiles: [{name: "notes.md", path: "/tmp/notes.md", size: 2048}],
    }),
  )
  const component = renderComponent()
  await simulate.sleep(0)

  component.querySelector("#choose-markdown").dispatchEvent("tap")
  await simulate.sleep(0)

  expect(wx.chooseMessageFile).toHaveBeenCalledWith(
    expect.objectContaining({count: 1, type: "file", extension: ["md"]}),
  )
  expect(component.dom.textContent).toContain("notes.md")
  expect(component.dom.textContent).toContain("2.0 KiB")
  expect(component.data.selectedScope).toBe("private")
  component.instance.selectScope({currentTarget: {dataset: {scope: "public"}}})
  expect(component.data.selectedScope).toBe("public")
})

test("locks duplicate submit, renders pending records, and refreshes after success", async () => {
  wx.request
    .mockImplementationOnce((options) =>
      options.success({statusCode: 200, data: EMPTY_COLLECTION}),
    )
    .mockImplementationOnce((options) =>
      options.success({
        statusCode: 200,
        data: {
          quota: {...EMPTY_COLLECTION.quota, daily_used: 1, effective_source_count: 1},
          items: [PUBLIC_SOURCE, LONG_PRIVATE_SOURCE],
        },
      }),
    )
  wx.chooseMessageFile.mockImplementation((options) =>
    options.success({
      tempFiles: [{name: "public.md", path: "/tmp/public.md", size: 100}],
    }),
  )
  let finishUpload
  wx.uploadFile.mockImplementation((options) => {
    finishUpload = () =>
      options.success({
        statusCode: 202,
        data: JSON.stringify({
          source: PUBLIC_SOURCE,
          quota: {
            ...EMPTY_COLLECTION.quota,
            daily_used: 1,
            effective_source_count: 1,
          },
        }),
      })
  })
  const component = renderComponent()
  await simulate.sleep(0)
  component.instance.chooseFile()
  component.instance.selectScope({currentTarget: {dataset: {scope: "public"}}})

  void component.instance.submitUpload()
  await simulate.sleep(0)
  void component.instance.submitUpload()
  expect(component.data.uploading).toBe(true)
  expect(wx.uploadFile).toHaveBeenCalledTimes(1)
  expect(wx.uploadFile.mock.calls[0][0].formData).toEqual({
    scope: "PUBLIC",
    original_filename: "public.md",
  })
  finishUpload()
  await simulate.sleep(0)
  await simulate.sleep(0)

  expect(wx.request).toHaveBeenCalledTimes(2)
  const text = component.dom.textContent
  expect(text).toContain("public.md")
  expect(text).toContain(
    "jdOpkWRtVw4r47e7f186c8827887b7342a81caaa2be4.md",
  )
  expect(text).toContain("正在提取知识点")
  expect(text).toContain("处理中")
  expect(text).toContain("public")
  expect(text).toContain("private")
  expect(text.indexOf("public.md")).toBeLessThan(
    text.indexOf("jdOpkWRtVw4r47e7f186c8827887b7342a81caaa2be4.md"),
  )
  expect(text).not.toContain("已完成")
  expect(text).not.toContain("个知识节点")
})

test("keeps records visible and disables upload when quota Problem Details is returned", async () => {
  const collection = {
    quota: {...EMPTY_COLLECTION.quota, daily_used: 1, effective_source_count: 1},
    items: [PRIVATE_SOURCE],
  }
  wx.request.mockImplementation((options) =>
    options.success({statusCode: 200, data: collection}),
  )
  wx.chooseMessageFile.mockImplementation((options) =>
    options.success({
      tempFiles: [{name: "next.md", path: "/tmp/next.md", size: 100}],
    }),
  )
  wx.uploadFile.mockImplementation((options) =>
    options.success({
      statusCode: 429,
      data: JSON.stringify({
        code: "daily_upload_limit_reached",
        quota: {...collection.quota, daily_used: 2},
      }),
    }),
  )
  const component = renderComponent()
  await simulate.sleep(0)
  component.instance.chooseFile()
  await component.instance.submitUpload()
  await simulate.sleep(0)

  const text = component.dom.textContent
  expect(text).toContain("private.md")
  expect(text).toContain("今日上传额度已用完")
  expect(text).toContain("当前额度已用尽")
  expect(component.data.quotaDisabled).toBe(true)
  expect(component.data.selectedFile.name).toBe("next.md")
})

test("recovers collection loading errors without fabricating records", async () => {
  wx.request
    .mockImplementationOnce((options) => options.fail())
    .mockImplementationOnce((options) =>
      options.success({statusCode: 200, data: EMPTY_COLLECTION}),
    )
  const component = renderComponent()
  await simulate.sleep(0)

  expect(component.dom.textContent).toContain("上传记录加载失败")
  expect(component.dom.textContent).not.toContain(".md")
  component.querySelector("#retry-collection").dispatchEvent("tap")
  await simulate.sleep(0)
  expect(component.dom.textContent).toContain("还没有知识资料")
})

test("clears owner records when the session is invalidated mid-use", async () => {
  const collection = {
    quota: {...EMPTY_COLLECTION.quota, daily_used: 1, effective_source_count: 1},
    items: [PRIVATE_SOURCE],
  }
  wx.request
    .mockImplementationOnce((options) =>
      options.success({statusCode: 200, data: collection}),
    )
    .mockImplementationOnce((options) => {
      options.success({statusCode: 401, data: {code: "authentication_required"}})
    })
  const component = renderComponent()
  await simulate.sleep(0)
  expect(component.dom.textContent).toContain("private.md")

  component.instance.retryCollection()
  await simulate.sleep(0)

  expect(component.data.items).toEqual([])
  expect(component.data.quota).toBeNull()
  expect(component.data.status).toBe("loading")
  expect(component.dom.textContent).not.toContain("private.md")
  expect(wx.reLaunch).toHaveBeenCalledWith({url: "/pages/login/index"})
})

function renderComponent() {
  const component = simulate.render(componentId)
  component.attach(document.body)
  return component
}
