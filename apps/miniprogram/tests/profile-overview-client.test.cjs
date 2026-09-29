const {
  ProfileOverviewRequestError,
  fetchProfileOverview,
} = require("../miniprogram/services/profile-overview.ts")
const {
  avatarInitials,
  formatExperience,
} = require("../miniprogram/utils/profile-overview.ts")

const OVERVIEW = {
  id: "user-1",
  nickname: "Lin Qiao",
  avatar_url: "https://example.invalid/lin.png",
  default_target_profile: {
    id: "profile-1",
    target_role: "Platform Engineer",
    relevant_experience_months: 27,
  },
  current_resume: null,
  recent_scores: [],
}

test("maps the overview request contract and sanitizes failures", async () => {
  const request = jest.fn((options) => {
    expect(options.url).toBe("http://127.0.0.1:8080/api/v1/me/overview")
    options.success({statusCode: 200, data: OVERVIEW})
  })

  await expect(fetchProfileOverview(request)).resolves.toEqual(OVERVIEW)

  const httpRequest = (options) => {
    options.success({statusCode: 503, data: {detail: "private upstream detail"}})
  }
  const networkRequest = (options) => {
    options.fail({errMsg: "request:fail private network detail"})
  }

  await expect(fetchProfileOverview(httpRequest)).rejects.toEqual(
    new ProfileOverviewRequestError("http_error"),
  )
  await expect(fetchProfileOverview(networkRequest)).rejects.toEqual(
    new ProfileOverviewRequestError("network_error"),
  )
})

test("formats experience and derives avatar initials from response values", () => {
  for (const [months, expected] of [
    [0, "0 个月"],
    [8, "8 个月"],
    [24, "2 年"],
    [27, "2 年 3 个月"],
  ]) {
    expect(formatExperience(months)).toBe(expected)
  }
  for (const [nickname, expected] of [
    ["Lin Qiao", "LQ"],
    ["包小明", "包小"],
    ["  ada   lovelace  ", "AL"],
    ["", "?"],
  ]) {
    expect(avatarInitials(nickname)).toBe(expected)
  }
})
