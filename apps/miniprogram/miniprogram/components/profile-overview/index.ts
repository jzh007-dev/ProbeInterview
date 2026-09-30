import {
  fetchProfileOverview,
  type ProfileOverview,
} from "../../services/profile-overview"
import {
  avatarInitials,
  formatExperience,
} from "../../utils/profile-overview"

export const PROFILE_ACTIONS = [
  "open-settings",
  "preview-current-resume",
  "open-score-history",
  "configure-interview-language",
  "open-privacy-data",
  "open-about",
] as const

export type ProfileAction = (typeof PROFILE_ACTIONS)[number]
type ViewStatus = "loading" | "success" | "error"

interface ProfileOverviewData {
  status: ViewStatus
  overview: ProfileOverview | null
  experienceLabel: string
  targetRoleLabel: string
  initials: string
  avatarFailed: boolean
  errorMessage: string
  lastAction: ProfileAction | ""
}

const INITIAL_DATA: ProfileOverviewData = {
  status: "loading",
  overview: null,
  experienceLabel: "",
  targetRoleLabel: "",
  initials: "",
  avatarFailed: false,
  errorMessage: "",
  lastAction: "",
}

function isProfileAction(value: unknown): value is ProfileAction {
  return (
    typeof value === "string" &&
    (PROFILE_ACTIONS as readonly string[]).includes(value)
  )
}

Component({
  data: INITIAL_DATA,

  lifetimes: {
    attached() {
      void this.loadOverview()
    },
  },

  methods: {
    async loadOverview() {
      this.setData({
        status: "loading",
        overview: null,
        experienceLabel: "",
        targetRoleLabel: "",
        initials: "",
        avatarFailed: false,
        errorMessage: "",
      })
      try {
        const overview = await fetchProfileOverview()
        const targetProfile = overview.default_target_profile
        this.setData({
          status: "success",
          overview,
          experienceLabel:
            targetProfile === null
              ? ""
              : formatExperience(targetProfile.relevant_experience_months),
          targetRoleLabel:
            targetProfile === null ? "尚未设置目标岗位" : targetProfile.target_role,
          initials: avatarInitials(overview.nickname),
        })
      } catch {
        this.setData({
          status: "error",
          overview: null,
          errorMessage: "个人概览加载失败，请稍后重试",
        })
      }
    },

    onRetry() {
      void this.loadOverview()
    },

    onAvatarError() {
      this.setData({ avatarFailed: true })
    },

    handleAction(
      event: WechatMiniprogram.CustomEvent<
        Record<string, never>,
        Record<string, never>,
        {action?: unknown}
      >,
    ) {
      const action = event.currentTarget.dataset.action
      if (!isProfileAction(action)) {
        return
      }
      if (
        action === "preview-current-resume" &&
        this.data.overview?.current_resume === null
      ) {
        return
      }
      this.setData({ lastAction: action })
    },
  },
})
