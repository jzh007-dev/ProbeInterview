const path = require("node:path")
const simulate = require("miniprogram-simulate")

const componentPath = path.resolve(
  __dirname,
  "../miniprogram/components/profile-overview/index",
)
let componentId

const WITH_RESUME = {
  id: "user-2",
  nickname: "Lin Qiao",
  avatar_url: "https://example.invalid/lin.png",
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

const WITHOUT_RESUME = {
  ...WITH_RESUME,
  current_resume: null,
}

beforeEach(() => {
  document.body.innerHTML = ""
  global.wx = {
    downloadFile: jest.fn(),
    navigateTo: jest.fn(),
    previewDocument: jest.fn(),
    request: jest.fn(),
    switchTab: jest.fn(),
    uploadFile: jest.fn(),
  }
})

beforeAll(() => {
  componentId = simulate.load(componentPath, {compiler: "simulate"})
})

test("renders loading, response values, resume metadata, and avatar fallback", async () => {
  let completeRequest
  wx.request.mockImplementation((options) => {
    completeRequest = () => options.success({statusCode: 200, data: WITH_RESUME})
  })
  const component = renderComponent()

  expect(component.dom.textContent).toContain("正在加载个人概览")
  expect(component.dom.textContent).not.toContain("Bao")
  expect(component.dom.textContent).not.toContain("AI 全栈开发")

  completeRequest()
  await simulate.sleep(0)

  expect(component.dom.textContent).toContain("Lin Qiao")
  expect(component.dom.textContent).toContain("Platform Engineer")
  expect(component.dom.textContent).toContain("2 年 3 个月")
  expect(component.dom.textContent).toContain("lin-profile.pdf")
  expect(component.querySelector("#preview-current-resume")).toBeDefined()

  component.querySelector(".avatar-image").dispatchEvent("error")
  await simulate.sleep(0)
  expect(component.dom.textContent).toContain("LQ")
})

test("recovers from an error into honest no-resume and empty-history states", async () => {
  wx.request
    .mockImplementationOnce((options) => options.fail({errMsg: "request:fail"}))
    .mockImplementationOnce((options) =>
      options.success({statusCode: 200, data: WITHOUT_RESUME}),
    )
  const component = renderComponent()

  await simulate.sleep(0)
  expect(component.dom.textContent).toContain("个人概览加载失败")
  expect(component.dom.textContent).not.toContain("暂无面试记录")

  component.querySelector("#retry-overview").dispatchEvent("tap")
  await simulate.sleep(0)

  expect(wx.request).toHaveBeenCalledTimes(2)
  const text = component.dom.textContent
  expect(text).toContain("尚未上传，将在模拟面试时添加")
  expect(text).toContain("暂无面试记录")
  expect(text).not.toContain(".pdf")
  expect(text).not.toContain("最近 5 次")
  expect(text).not.toContain("更换")
  expect(text).not.toContain("上传简历")
  expect(component.querySelector(".trend-line")).toBeUndefined()
  expect(component.querySelector("#preview-current-resume")).toBeUndefined()
})

test("recognizes reserved actions without navigation, files, or mutation", async () => {
  wx.request.mockImplementation((options) => {
    options.success({statusCode: 200, data: WITH_RESUME})
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
    expect(component.data.lastAction).toBe(action)
  }

  expect(wx.navigateTo).not.toHaveBeenCalled()
  expect(wx.switchTab).not.toHaveBeenCalled()
  expect(wx.previewDocument).not.toHaveBeenCalled()
  expect(wx.uploadFile).not.toHaveBeenCalled()
  expect(wx.downloadFile).not.toHaveBeenCalled()
  expect(wx.request).toHaveBeenCalledTimes(1)
})

function renderComponent() {
  const component = simulate.render(componentId)
  component.attach(document.body)
  return component
}
