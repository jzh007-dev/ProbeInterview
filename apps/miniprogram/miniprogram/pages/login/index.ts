import {
  createInitialLoginState,
  transition,
  type LoginEvent,
  type LoginState,
} from "./login-machine"
import {readValidSessionPair} from "../../services/auth-state"
import {
  completeRegistration,
  startWechatLogin,
} from "../../services/login-coordinator"
import {
  describeLoginError,
  LoginError,
  validateLoginNickname,
} from "../../utils/login"

const HOME_TAB_URL = "/pages/index/index"

Page({
  data: {
    state: createInitialLoginState(),
  },

  onLoad() {
    // Startup never calls wx.login: a valid cache pair enters the app
    // directly, anything else stays on the login page.
    if (readValidSessionPair() !== null) {
      this.enterHome()
    }
  },

  onLoginTap() {
    if (!this.dispatch({type: "start_exchange"})) {
      return
    }
    void this.runExchange()
  },

  onNicknameInput(event: {detail: {value?: unknown}}) {
    const value = event.detail.value
    if (typeof value !== "string") {
      return
    }
    this.dispatch({type: "edit_nickname", nickname: value})
  },

  onChooseAvatar(event: {detail: {avatarUrl?: unknown}}) {
    const path = event.detail.avatarUrl
    if (typeof path !== "string" || path === "") {
      return
    }
    this.dispatch({type: "choose_avatar", tempFilePath: path})
  },

  onChooseDefaultAvatar() {
    this.dispatch({type: "choose_default_avatar"})
  },

  onSubmitRegistration() {
    const nickname = validateLoginNickname(this.data.state.nickname)
    if (nickname === null) {
      this.dispatch({
        type: "registration_blocked",
        message: "请输入 1 到 200 个字符的昵称",
      })
      return
    }
    if (!this.dispatch({type: "start_registration"})) {
      return
    }
    void this.runRegistration(nickname)
  },

  dispatch(event: LoginEvent): boolean {
    const nextState: LoginState = transition(this.data.state, event)
    if (nextState === this.data.state) {
      return false
    }
    this.setData({state: nextState})
    return true
  },

  async runExchange() {
    try {
      const outcome = await startWechatLogin()
      if (outcome.kind === "authenticated") {
        this.dispatch({type: "exchange_authenticated"})
        this.enterHome()
        return
      }
      this.dispatch({
        type: "exchange_registration_required",
        registrationToken: outcome.registrationToken,
      })
    } catch (error) {
      this.dispatch({type: "exchange_failed", message: describeLoginError(error)})
    }
  },

  async runRegistration(nickname: string) {
    const registrationToken = this.data.state.registrationToken
    if (registrationToken === null) {
      return
    }
    try {
      await completeRegistration({
        registrationToken,
        nickname,
        avatarFilePath: this.data.state.avatarTempPath,
      })
      this.dispatch({type: "registration_succeeded"})
      this.enterHome()
    } catch (error) {
      const requiresRelogin =
        error instanceof LoginError &&
        (error.problemCode === "registration_token_invalid" ||
          error.code === "unauthorized")
      this.dispatch({
        type: "registration_failed",
        message: describeLoginError(error),
        requiresRelogin,
      })
    }
  },

  enterHome() {
    wx.switchTab({url: HOME_TAB_URL})
  },
})
