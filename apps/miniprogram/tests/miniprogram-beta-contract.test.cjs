const fs = require("node:fs")
const path = require("node:path")

const componentRoot = path.resolve(__dirname, "../miniprogram/components")
const repositoryRoot = path.resolve(__dirname, "../../..")
const forbiddenTags = [
  "button",
  "image",
  "scroll-view",
  "swiper",
  "swiper-item",
  "text",
  "view",
]

test("custom-component WXSS uses selectors accepted by the WeChat compiler", () => {
  const failures = []

  for (const filePath of findWxssFiles(componentRoot)) {
    const stylesheet = fs.readFileSync(filePath, "utf8")
    for (const selector of extractSelectors(stylesheet)) {
      if (/#[-\w]+/.test(selector)) {
        failures.push(`${relative(filePath)}: ID selector ${selector}`)
      }
      if (/\[[^\]]+]/.test(selector)) {
        failures.push(`${relative(filePath)}: attribute selector ${selector}`)
      }
      const tagPattern = new RegExp(
        `(^|[\\s>+~])(?:${forbiddenTags.join("|")})(?=[:.\\s>+~#\\[]|$)`,
      )
      if (tagPattern.test(selector)) {
        failures.push(`${relative(filePath)}: tag selector ${selector}`)
      }
    }
  }

  expect(failures).toEqual([])
})

test("upload history contains long filenames and keeps status and scope visible", () => {
  const template = fs.readFileSync(
    path.join(
      componentRoot,
      "knowledge-source-manager",
      "index.wxml",
    ),
    "utf8",
  )
  const stylesheet = fs.readFileSync(
    path.join(
      componentRoot,
      "knowledge-source-manager",
      "index.wxss",
    ),
    "utf8",
  )

  expect(template).toContain('class="processing-tag"')
  expect(template).toContain("处理中")
  expect(template).toContain('class="scope-tag {{item.scopeLabel}}"')
  expect(ruleBody(stylesheet, ".history-item")).toMatch(/\boverflow:\s*hidden\b/)
  expect(ruleBody(stylesheet, ".history-name")).toMatch(
    /\btext-overflow:\s*ellipsis\b/,
  )
  expect(ruleBody(stylesheet, ".history-name")).toMatch(/\bmax-width:\s*100%/)
  expect(ruleBody(stylesheet, ".history-title-row")).toMatch(
    /\bdisplay:\s*flex\b/,
  )
  expect(ruleBody(stylesheet, ".history-meta")).toMatch(/\bdisplay:\s*flex\b/)
  expect(ruleBody(stylesheet, ".history-meta")).toMatch(
    /\bjustify-content:\s*space-between\b/,
  )
  expect(ruleBody(stylesheet, ".processing-tag")).toMatch(
    /\bflex:\s*0 0 auto\b/,
  )
  expect(ruleBody(stylesheet, ".processing-tag")).toMatch(
    /\bbackground:\s*#ece6f8\b/,
  )
  expect(ruleBody(stylesheet, ".processing-tag")).toMatch(
    /\bfont-size:\s*24rpx\b/,
  )
})

test("running-development beta smoke carries a session but stays read-only for product data", () => {
  const script = fs.readFileSync(
    path.join(repositoryRoot, "scripts", "test-beta-smoke"),
    "utf8",
  )

  expect(script).toContain("/api/v1/auth/wechat/exchanges")
  expect(script).toContain("Authorization: Bearer ${bearer_token}")
  expect(script).toContain("/api/v1/me/knowledge-sources")
  expect(script).not.toContain("Idempotency-Key")
  expect(script).not.toContain(' -F "')
  expect(script).not.toContain("--request POST")
})

function findWxssFiles(directory) {
  return fs.readdirSync(directory, {withFileTypes: true}).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name)
    if (entry.isDirectory()) return findWxssFiles(entryPath)
    return entry.name.endsWith(".wxss") ? [entryPath] : []
  })
}

function extractSelectors(stylesheet) {
  const selectors = []
  for (const match of stylesheet.matchAll(/([^{}]+)\{/g)) {
    const group = match[1].trim()
    if (!group || group.startsWith("@")) continue
    selectors.push(...group.split(",").map((selector) => selector.trim()))
  }
  return selectors
}

function relative(filePath) {
  return path.relative(path.resolve(__dirname, ".."), filePath)
}

function ruleBody(stylesheet, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  return Array.from(
    stylesheet.matchAll(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`, "g")),
    (match) => match[1],
  ).join("\n")
}
