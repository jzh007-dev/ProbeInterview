const {
  createInitialLoginState,
  transition,
} = require("../miniprogram/pages/login/login-machine.ts")
const {
  describeLoginError,
  LoginError,
} = require("../miniprogram/utils/login.ts")

const REGISTRATION_TOKEN = "reg-token-1"

function exchangedState() {
  const exchanging = transition(createInitialLoginState(), {type: "start_exchange"})
  return transition(
    exchanging,
    {type: "exchange_registration_required", registrationToken: REGISTRATION_TOKEN},
  )
}

test("walks the authenticated path from idle to success", () => {
  let state = createInitialLoginState()
  state = transition(state, {type: "start_exchange"})
  expect(state.phase).toBe("exchanging")
  state = transition(state, {type: "exchange_authenticated"})
  expect(state.phase).toBe("success")
})

test("walks the registration path with avatar choices preserved", () => {
  let state = transition(createInitialLoginState(), {type: "start_exchange"})
  state = transition(state, {
    type: "exchange_registration_required",
    registrationToken: REGISTRATION_TOKEN,
  })
  expect(state.phase).toBe("registration_required")
  expect(state.registrationToken).toBe(REGISTRATION_TOKEN)
  expect(state.avatarTempPath).toBeNull()

  state = transition(state, {type: "edit_nickname", nickname: "包小明"})
  state = transition(state, {type: "choose_avatar", tempFilePath: "wxfile://tmp/a.png"})
  expect(state.nickname).toBe("包小明")
  expect(state.avatarTempPath).toBe("wxfile://tmp/a.png")

  // 无文件的显式选择：显式选择默认头像会清掉已选的临时头像
  state = transition(state, {type: "choose_default_avatar"})
  expect(state.avatarTempPath).toBeNull()
  state = transition(state, {type: "choose_avatar", tempFilePath: "wxfile://tmp/b.png"})

  state = transition(state, {type: "start_registration"})
  expect(state.phase).toBe("registering")
  state = transition(state, {type: "registration_succeeded"})
  expect(state.phase).toBe("success")
})

test("keeps the form editable and populated when registration fails recoverably", () => {
  let state = exchangedState()
  state = transition(state, {type: "edit_nickname", nickname: "Lin Qiao"})
  state = transition(state, {type: "choose_avatar", tempFilePath: "wxfile://tmp/a.png"})
  state = transition(state, {type: "start_registration"})
  state = transition(state, {
    type: "registration_failed",
    message: "头像存储暂时不可用，请稍后重试",
    requiresRelogin: false,
  })

  expect(state.phase).toBe("registration_required")
  expect(state.nickname).toBe("Lin Qiao")
  expect(state.avatarTempPath).toBe("wxfile://tmp/a.png")
  expect(state.registrationToken).toBe(REGISTRATION_TOKEN)
  expect(state.errorMessage).toBe("头像存储暂时不可用，请稍后重试")
})

test("consumed credentials fall back to a fresh login instead of the form", () => {
  let state = exchangedState()
  state = transition(state, {type: "start_registration"})
  state = transition(state, {
    type: "registration_failed",
    message: "注册凭证已过期，请重新登录",
    requiresRelogin: true,
  })

  expect(state.phase).toBe("error")
  expect(state.registrationToken).toBeNull()

  state = transition(state, {type: "start_exchange"})
  expect(state.phase).toBe("exchanging")
})

test("blocks duplicate submits in every busy phase", () => {
  const exchanging = transition(createInitialLoginState(), {type: "start_exchange"})
  expect(transition(exchanging, {type: "start_exchange"})).toBe(exchanging)

  const registering = transition(exchangedState(), {type: "start_registration"})
  expect(transition(registering, {type: "start_registration"})).toBe(registering)
  expect(transition(registering, {type: "start_exchange"})).toBe(registering)
  expect(transition(registering, {type: "edit_nickname", nickname: "x"})).toBe(registering)
})

test("ignores out-of-phase events instead of corrupting the machine", () => {
  const idle = createInitialLoginState()
  expect(transition(idle, {type: "exchange_authenticated"})).toBe(idle)
  expect(transition(idle, {type: "start_registration"})).toBe(idle)
  expect(transition(idle, {type: "choose_avatar", tempFilePath: "p"})).toBe(idle)

  const registering = transition(exchangedState(), {type: "start_registration"})
  expect(transition(registering, {type: "registration_succeeded", })).not.toBe(registering)
  const done = transition(registering, {type: "registration_succeeded"})
  expect(transition(done, {type: "exchange_failed", message: "x"})).toBe(done)
})

test("surfaces only safe error copy for every login failure", () => {
  const failures = [
    [new LoginError("wechat_login_failed"), "微信登录失败，请重试"],
    [new LoginError("network_error"), "网络连接失败，请稍后重试"],
    [new LoginError("invalid_response"), "登录响应异常，请稍后重试"],
    [
      new LoginError("request_failed", "wechat_code_exchange_failed"),
      "微信登录失败，请重试",
    ],
    [
      new LoginError("request_failed", "registration_token_invalid"),
      "注册凭证已过期，请重新登录",
    ],
    [
      new LoginError("request_failed", "storage_unavailable"),
      "头像存储暂时不可用，请稍后重试",
    ],
    [new Error("secret upstream stack"), "操作失败，请稍后重试"],
  ]

  for (const [error, expected] of failures) {
    expect(describeLoginError(error)).toBe(expected)
  }

  let state = transition(createInitialLoginState(), {type: "start_exchange"})
  state = transition(state, {
    type: "exchange_failed",
    message: describeLoginError(new Error("request:fail private detail")),
  })
  expect(state.errorMessage).toBe("操作失败，请稍后重试")
})
