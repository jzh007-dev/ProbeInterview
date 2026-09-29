const fs = require("node:fs")
const path = require("node:path")
const simulate = require("miniprogram-simulate")

const root = path.resolve(__dirname, "../miniprogram")
let profileComponentId

beforeAll(() => {
  const componentPath = path.join(root, "components/profile-overview/index")
  profileComponentId = simulate.load(componentPath, {compiler: "simulate"})
})

test("declares every native tab route, loads its shell, and keeps profile loadable", () => {
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
  for (const tab of app.tabBar.list) {
    expect(fs.existsSync(path.join(root, tab.iconPath))).toBe(true)
    expect(fs.existsSync(path.join(root, tab.selectedIconPath))).toBe(true)
  }
  for (const [pagePath] of expected) {
    for (const extension of ["json", "ts", "wxml", "wxss"]) {
      expect(fs.existsSync(path.join(root, `${pagePath}.${extension}`))).toBe(true)
    }
  }
  for (const [pagePath] of expected.slice(0, 4)) {
    expect(fs.readFileSync(path.join(root, `${pagePath}.wxml`), "utf8")).toContain(
      "page-shell",
    )
  }
  const profileWxml = fs.readFileSync(
    path.join(root, "pages/profile/index.wxml"),
    "utf8",
  )
  expect(profileWxml).toContain("<profile-overview")

  expect(simulate.render(profileComponentId)).toBeDefined()
})

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(root, relativePath), "utf8"))
}
