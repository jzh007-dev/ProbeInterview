import {
  currentUserSnapshotFromOverview,
  readCurrentUserSnapshot,
  writeCurrentUserSnapshot,
  type CurrentUserSnapshot,
} from "../../services/current-user-store"
import {
  describeProfileError,
  fetchProfileOverview,
  putDefaultTargetProfile,
  type ProfileOverview,
} from "../../services/profile-overview"
import {
  avatarInitials,
  formatExperience,
  parseExperienceMonthsInput,
  validateTargetRoleInput,
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
  viewer: CurrentUserSnapshot | null
  overview: ProfileOverview | null
  experienceLabel: string
  targetRoleLabel: string
  initials: string
  avatarFailed: boolean
  errorMessage: string
  profileRoleInput: string
  profileMonthsInput: string
  profileFormTouched: boolean
  profileSaving: boolean
  profileError: string
  profileNotice: string
  lastAction: ProfileAction | ""
}

const INITIAL_DATA: ProfileOverviewData = {
  status: "loading",
  viewer: null,
  overview: null,
  experienceLabel: "",
  targetRoleLabel: "",
  initials: "",
  avatarFailed: false,
  errorMessage: "",
  profileRoleInput: "",
  profileMonthsInput: "",
  profileFormTouched: false,
  profileSaving: false,
  profileError: "",
  profileNotice: "",
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
      this.seedFromCache()
      void this.loadOverview()
    },
  },

  methods: {
    seedFromCache() {
      const snapshot = readCurrentUserSnapshot()
      if (snapshot === null) {
        return
      }
      this.applyViewer(snapshot)
    },

    applyViewer(snapshot: CurrentUserSnapshot) {
      const profile = snapshot.defaultTargetProfile
      this.setData({
        status: "success",
        viewer: snapshot,
        initials: avatarInitials(snapshot.nickname),
        experienceLabel:
          profile === null ? "" : formatExperience(profile.relevantExperienceMonths),
        targetRoleLabel:
          profile === null ? "尚未设置目标岗位" : profile.targetRole,
      })
      if (!this.data.profileFormTouched) {
        this.setData({
          profileRoleInput: profile === null ? "" : profile.targetRole,
          profileMonthsInput:
            profile === null ? "" : String(profile.relevantExperienceMonths),
        })
      }
    },

    async loadOverview() {
      if (this.data.viewer === null) {
        this.setData({status: "loading", errorMessage: ""})
      }
      try {
        const overview = await fetchProfileOverview()
        const snapshot = writeCurrentUserSnapshot(
          currentUserSnapshotFromOverview(overview),
        )
        this.setData({overview, avatarFailed: false, errorMessage: ""})
        this.applyViewer(snapshot)
      } catch (error) {
        if (this.data.viewer !== null) {
          // Stale cache content stays visible; the next show retries.
          return
        }
        this.setData({
          status: "error",
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

    onProfileRoleInput(event: {detail: {value?: unknown}}) {
      const value = event.detail.value
      if (typeof value !== "string") {
        return
      }
      this.setData({profileRoleInput: value, profileFormTouched: true})
    },

    onProfileMonthsInput(event: {detail: {value?: unknown}}) {
      const value = event.detail.value
      if (typeof value !== "string") {
        return
      }
      this.setData({profileMonthsInput: value, profileFormTouched: true})
    },

    async onSaveProfile() {
      if (this.data.profileSaving || this.data.viewer === null) {
        return
      }
      const targetRole = validateTargetRoleInput(this.data.profileRoleInput)
      if (targetRole === null) {
        this.setData({
          profileError: "目标岗位需为 1 到 200 个字符",
          profileNotice: "",
        })
        return
      }
      const months = parseExperienceMonthsInput(this.data.profileMonthsInput)
      if (months === null) {
        this.setData({
          profileError: "经验月数需为 0 到 600 的整数",
          profileNotice: "",
        })
        return
      }

      this.setData({profileSaving: true, profileError: "", profileNotice: ""})
      try {
        const saved = await putDefaultTargetProfile({
          targetRole,
          relevantExperienceMonths: months,
        })
        // One validated cache write carries both the saved profile and the
        // rest of the display snapshot, so home observes it atomically.
        const updated = writeCurrentUserSnapshot({
          ...this.data.viewer,
          defaultTargetProfile: {
            targetRole: saved.target_role,
            relevantExperienceMonths: saved.relevant_experience_months,
          },
        })
        this.setData({
          viewer: updated,
          overview:
            this.data.overview === null
              ? null
              : {...this.data.overview, default_target_profile: saved},
          experienceLabel: formatExperience(saved.relevant_experience_months),
          targetRoleLabel: saved.target_role,
          profileNotice: "目标画像已保存",
        })
      } catch (error) {
        // Inputs and the previous cache stay untouched on failure.
        this.setData({profileError: describeProfileError(error)})
      } finally {
        this.setData({profileSaving: false})
      }
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
