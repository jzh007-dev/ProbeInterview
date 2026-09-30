const fs = require("node:fs")
const path = require("node:path")
const zlib = require("node:zlib")
const simulate = require("miniprogram-simulate")

const root = path.resolve(__dirname, "../miniprogram")
let profileComponentId
let homeComponentId
let uploadComponentId

beforeAll(() => {
  const homeComponentPath = path.join(
    root,
    "components/home-knowledge-overview/index",
  )
  const componentPath = path.join(root, "components/profile-overview/index")
  const uploadComponentPath = path.join(
    root,
    "components/knowledge-source-manager/index",
  )
  homeComponentId = simulate.load(homeComponentPath, {compiler: "simulate"})
  profileComponentId = simulate.load(componentPath, {compiler: "simulate"})
  uploadComponentId = simulate.load(uploadComponentPath, {compiler: "simulate"})
})

test("declares native tab state, renders home, and preserves the remaining routes", () => {
  const app = readJson("app.json")
  const project = readProjectJson("project.config.json")
  const expected = [
    ["pages/index/index", "首页"],
    ["pages/review/index", "复盘"],
    ["pages/simulation/index", "模拟"],
    ["pages/upload/index", "上传"],
    ["pages/profile/index", "我的"],
  ]

  expect(app.tabBar.list.map(({pagePath, text}) => [pagePath, text])).toEqual(expected)
  expect(app.pages).toEqual(["pages/login/index", ...expected.map(([pagePath]) => pagePath)])
  expect(app.tabBar.selectedColor).toBe("#334039")
  expect(project.setting.urlCheck).toBe(false)
  const iconPaths = []
  for (const tab of app.tabBar.list) {
    expect(tab.iconPath).not.toBe(tab.selectedIconPath)
    expect(fs.existsSync(path.join(root, tab.iconPath))).toBe(true)
    expect(fs.existsSync(path.join(root, tab.selectedIconPath))).toBe(true)
    expectTabIcon(tab.iconPath, app.tabBar.color)
    expectTabIcon(tab.selectedIconPath, app.tabBar.selectedColor)
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

  for (const [pagePath] of expected.slice(1, 3)) {
    expect(fs.readFileSync(path.join(root, `${pagePath}.wxml`), "utf8")).toContain(
      "page-shell",
    )
    expect(fs.readFileSync(path.join(root, `${pagePath}.wxss`), "utf8")).toContain(
      '@import "../../styles/page-shell.wxss";',
    )
  }
  const pageShellStyles = fs.readFileSync(
    path.join(root, "styles/page-shell.wxss"),
    "utf8",
  )
  expect(pageShellStyles).toContain(".page-shell")
  expect(pageShellStyles).toContain(".title")
  expect(pageShellStyles).toContain(".description")
  const profileWxml = fs.readFileSync(
    path.join(root, "pages/profile/index.wxml"),
    "utf8",
  )
  expect(profileWxml).toContain("<profile-overview")
  const uploadWxml = fs.readFileSync(
    path.join(root, "pages/upload/index.wxml"),
    "utf8",
  )
  expect(uploadWxml).toContain("<knowledge-source-manager")
  expect(uploadWxml).not.toContain("page-shell")

  expect(simulate.render(homeComponentId)).toBeDefined()
  expect(simulate.render(profileComponentId)).toBeDefined()
  expect(simulate.render(uploadComponentId)).toBeDefined()
})

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(root, relativePath), "utf8"))
}

function readProjectJson(relativePath) {
  return JSON.parse(
    fs.readFileSync(path.resolve(root, "..", relativePath), "utf8"),
  )
}

function expectTabIcon(relativePath, expectedColor) {
  const metrics = readPngMetrics(path.join(root, relativePath))

  expect([metrics.width, metrics.height]).toEqual([48, 48])
  expect(metrics.visibleWidth).toBeGreaterThanOrEqual(24)
  expect(metrics.visibleHeight).toBeGreaterThanOrEqual(24)
  expect(Math.abs(metrics.centerX - 23.5)).toBeLessThanOrEqual(5)
  expect(Math.abs(metrics.centerY - 23.5)).toBeLessThanOrEqual(5)
  expect(colorDistance(metrics.averageColor, parseHexColor(expectedColor))).toBeLessThan(
    12,
  )
}

function readPngMetrics(filePath) {
  const png = fs.readFileSync(filePath)
  const signature = png.subarray(0, 8)
  expect(signature.equals(Buffer.from("89504e470d0a1a0a", "hex"))).toBe(true)

  let offset = 8
  let width = 0
  let height = 0
  const idat = []
  while (offset < png.length) {
    const length = png.readUInt32BE(offset)
    const type = png.toString("ascii", offset + 4, offset + 8)
    const data = png.subarray(offset + 8, offset + 8 + length)
    if (type === "IHDR") {
      width = data.readUInt32BE(0)
      height = data.readUInt32BE(4)
      expect([...data.subarray(8, 13)]).toEqual([8, 6, 0, 0, 0])
    } else if (type === "IDAT") {
      idat.push(data)
    }
    offset += length + 12
  }

  const scanlines = zlib.inflateSync(Buffer.concat(idat))
  const stride = width * 4
  const pixels = Buffer.alloc(stride * height)
  let sourceOffset = 0
  for (let y = 0; y < height; y += 1) {
    const filter = scanlines[sourceOffset]
    sourceOffset += 1
    for (let x = 0; x < stride; x += 1) {
      const raw = scanlines[sourceOffset + x]
      const left = x >= 4 ? pixels[y * stride + x - 4] : 0
      const up = y > 0 ? pixels[(y - 1) * stride + x] : 0
      const upperLeft = y > 0 && x >= 4 ? pixels[(y - 1) * stride + x - 4] : 0
      pixels[y * stride + x] = unfilter(raw, filter, left, up, upperLeft)
    }
    sourceOffset += stride
  }

  let minX = width
  let minY = height
  let maxX = -1
  let maxY = -1
  let alphaWeight = 0
  const colorTotals = [0, 0, 0]
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const pixelOffset = y * stride + x * 4
      const alpha = pixels[pixelOffset + 3]
      if (!alpha) continue
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x)
      maxY = Math.max(maxY, y)
      alphaWeight += alpha
      for (let channel = 0; channel < 3; channel += 1) {
        colorTotals[channel] += pixels[pixelOffset + channel] * alpha
      }
    }
  }

  return {
    width,
    height,
    visibleWidth: maxX - minX + 1,
    visibleHeight: maxY - minY + 1,
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2,
    averageColor: colorTotals.map((total) => total / alphaWeight),
  }
}

function unfilter(raw, filter, left, up, upperLeft) {
  if (filter === 0) return raw
  if (filter === 1) return (raw + left) & 0xff
  if (filter === 2) return (raw + up) & 0xff
  if (filter === 3) return (raw + Math.floor((left + up) / 2)) & 0xff
  if (filter === 4) return (raw + paeth(left, up, upperLeft)) & 0xff
  throw new Error(`Unsupported PNG filter: ${filter}`)
}

function paeth(left, up, upperLeft) {
  const prediction = left + up - upperLeft
  const leftDistance = Math.abs(prediction - left)
  const upDistance = Math.abs(prediction - up)
  const upperLeftDistance = Math.abs(prediction - upperLeft)
  if (leftDistance <= upDistance && leftDistance <= upperLeftDistance) return left
  if (upDistance <= upperLeftDistance) return up
  return upperLeft
}

function parseHexColor(value) {
  return [1, 3, 5].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16))
}

function colorDistance(actual, expected) {
  return Math.sqrt(
    actual.reduce((sum, channel, index) => sum + (channel - expected[index]) ** 2, 0),
  )
}
