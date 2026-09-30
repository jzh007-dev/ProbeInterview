export type LoginPhase =
  | "idle"
  | "exchanging"
  | "registration_required"
  | "registering"
  | "error"
  | "success"

export interface LoginState {
  phase: LoginPhase
  nickname: string
  avatarTempPath: string | null
  registrationToken: string | null
  errorMessage: string
}

export type LoginEvent =
  | {type: "start_exchange"}
  | {type: "exchange_authenticated"}
  | {type: "exchange_registration_required"; registrationToken: string}
  | {type: "exchange_failed"; message: string}
  | {type: "edit_nickname"; nickname: string}
  | {type: "choose_avatar"; tempFilePath: string}
  | {type: "choose_default_avatar"}
  | {type: "start_registration"}
  | {type: "registration_blocked"; message: string}
  | {type: "registration_succeeded"}
  | {type: "registration_failed"; message: string; requiresRelogin: boolean}

export function createInitialLoginState(): LoginState {
  return {
    phase: "idle",
    nickname: "",
    avatarTempPath: null,
    registrationToken: null,
    errorMessage: "",
  }
}

export function transition(
  state: LoginState,
  event: LoginEvent,
): LoginState {
  switch (event.type) {
    case "start_exchange": {
      if (state.phase !== "idle" && state.phase !== "error") {
        return state
      }
      return {...state, phase: "exchanging", errorMessage: ""}
    }
    case "exchange_authenticated": {
      if (state.phase !== "exchanging") {
        return state
      }
      return {...state, phase: "success", errorMessage: ""}
    }
    case "exchange_registration_required": {
      if (state.phase !== "exchanging") {
        return state
      }
      return {
        ...state,
        phase: "registration_required",
        registrationToken: event.registrationToken,
        nickname: "",
        avatarTempPath: null,
        errorMessage: "",
      }
    }
    case "exchange_failed": {
      if (state.phase !== "exchanging") {
        return state
      }
      return {...state, phase: "error", errorMessage: event.message}
    }
    case "edit_nickname": {
      if (state.phase !== "registration_required") {
        return state
      }
      return {...state, nickname: event.nickname}
    }
    case "choose_avatar": {
      if (state.phase !== "registration_required") {
        return state
      }
      return {
        ...state,
        avatarTempPath: event.tempFilePath,
        errorMessage: "",
      }
    }
    case "choose_default_avatar": {
      if (state.phase !== "registration_required") {
        return state
      }
      return {...state, avatarTempPath: null, errorMessage: ""}
    }
    case "start_registration": {
      if (
        state.phase !== "registration_required" ||
        state.registrationToken === null
      ) {
        return state
      }
      return {...state, phase: "registering", errorMessage: ""}
    }
    case "registration_blocked": {
      if (state.phase !== "registration_required") {
        return state
      }
      return {...state, errorMessage: event.message}
    }
    case "registration_succeeded": {
      if (state.phase !== "registering") {
        return state
      }
      return {...state, phase: "success", errorMessage: ""}
    }
    case "registration_failed": {
      if (state.phase !== "registering") {
        return state
      }
      if (event.requiresRelogin) {
        return {
          ...state,
          phase: "error",
          registrationToken: null,
          errorMessage: event.message,
        }
      }
      return {...state, phase: "registration_required", errorMessage: event.message}
    }
  }
}
