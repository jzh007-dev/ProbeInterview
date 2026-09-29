const fs = require("node:fs")
const path = require("node:path")
const simulate = require("miniprogram-simulate")

const root = path.resolve(__dirname, "../miniprogram")
let profileComponentId
let homeComponentId

beforeAll(() => {
  const homeComponentPath = path.join(
    root,
    "components/home-knowledge-overview/index",
  )
  const componentPath = path.join(root, "components/profile-overview/index")
  homeComponentId = simulate.load(homeComponentPath, {compiler: "simulate"})
  profileComponentId = simulate.load(componentPath, {compiler: "simulate"})
})

test("declares native tab state, renders home, and preserves the remaining routes", () => {
  const app = readJson("app.json")
  const expected = [
    ["pages/index/index", "首页"],
    ["pages/review/index", "复盘"],
    ["pages/simulation/index", "模拟"],
    ["pages/upload/index", "上传"],
    ["pages/profile/index", "我的"],
  ]

  expect(app.tabBar.list.map(({pagePath, text}) => [pagePath, text])).toEqual(expected)
  expect(app.pages).toEqual(expected.map(([pagePath]) => pagePath))
  expect(app.tabBar.selectedColor).toBe("#334039")
  const iconPaths = []
  for (const tab of app.tabBar.list) {
    expect(tab.iconPath).not.toBe(tab.selectedIconPath)
    expect(fs.existsSync(path.join(root, tab.iconPath))).toBe(true)
    expect(fs.existsSync(path.join(root, tab.selectedIconPath))).toBe(true)
    iconPaths.push(tab.iconPath, tab.selectedIconPath)
  }
  expect(new Set(iconPaths)).toHaveProperty("size", 10)
  for (const [pagePath] of expected) {
    for (const extension of ["json", "ts", "wxml", "wxss"]) {
      expect(fs.existsSync(path.join(root, `${pagePath}.${extension}`))).toBe(true)
    }
  }
  const homeWxml = fs.readFileSync(
    path.join(root, "pages/index/index.wxml"),
    "utf8",
  )
  expect(homeWxml).toContain("<home-knowledge-overview")
  expect(homeWxml).not.toContain("page-shell")

  for (const [pagePath] of expected.slice(1, 4)) {
    expect(fs.readFileSync(path.join(root, `${pagePath}.wxml`), "utf8")).toContain(
      "page-shell",
    )
  }
  const profileWxml = fs.readFileSync(
    path.join(root, "pages/profile/index.wxml"),
    "utf8",
  )
  expect(profileWxml).toContain("<profile-overview")

  expect(simulate.render(homeComponentId)).toBeDefined()
  expect(simulate.render(profileComponentId)).toBeDefined()
})

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(root, relativePath), "utf8"))
}
