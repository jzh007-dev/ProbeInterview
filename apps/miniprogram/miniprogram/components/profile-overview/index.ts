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
import {avatarInitials, formatExperience} from "../../utils/profile-overview"

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

// The role catalogue is fixed until the role-normalization feature lands;
// the picker keeps the write contract to known display-safe values.
export const TARGET_ROLE_OPTIONS = ["AI 全栈开发"] as const
export const TARGET_EXPERIENCE_YEARS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const

interface ProfileOverviewData {
  status: ViewStatus
  viewer: CurrentUserSnapshot | null
  overview: ProfileOverview | null
  experienceLabel: string
  targetRoleLabel: string
  initials: string
  avatarFailed: boolean
  errorMessage: string
  targetRoleOptions: string[]
  targetYearsOptions: string[]
  profileFormOpen: boolean
  profileRoleIndex: number
  profileYearsIndex: number
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
  targetRoleOptions: [...TARGET_ROLE_OPTIONS],
  targetYearsOptions: TARGET_EXPERIENCE_YEARS.map((years) => `${years} 年`),
  profileFormOpen: false,
  profileRoleIndex: 0,
  profileYearsIndex: 0,
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
      const formOpen = this.data.profileFormOpen
      this.setData({
        status: "success",
        viewer: snapshot,
        initials: avatarInitials(snapshot.nickname),
        experienceLabel:
          profile === null ? "" : formatExperience(profile.relevantExperienceMonths),
        targetRoleLabel:
          profile === null ? "尚未设置目标岗位" : profile.targetRole,
      })
      if (!formOpen) {
        this.setData({
          profileRoleIndex: 0,
          profileYearsIndex:
            profile === null
              ? 0
              : Math.max(
                  0,
                  TARGET_EXPERIENCE_YEARS.findIndex(
                    (years) => years * 12 === profile.relevantExperienceMonths,
                  ),
                ),
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

    onEditProfile() {
      const profile = this.data.viewer?.defaultTargetProfile ?? null
      this.setData({
        profileFormOpen: true,
        profileError: "",
        profileNotice: "",
        profileRoleIndex: 0,
        profileYearsIndex:
          profile === null
            ? 0
            : Math.max(
                0,
                TARGET_EXPERIENCE_YEARS.findIndex(
                  (years) => years * 12 === profile.relevantExperienceMonths,
                ),
              ),
      })
    },

    onProfileRoleChange(event: {detail: {value?: unknown}}) {
      const index = event.detail.value
      if (typeof index !== "number" || !Number.isInteger(index)) {
        return
      }
      this.setData({profileRoleIndex: index})
    },

    onProfileYearsChange(event: {detail: {value?: unknown}}) {
      const index = event.detail.value
      if (typeof index !== "number" || !Number.isInteger(index)) {
        return
      }
      this.setData({profileYearsIndex: index})
    },

    async onSaveProfile() {
      if (this.data.profileSaving || this.data.viewer === null) {
        return
      }
      const role = TARGET_ROLE_OPTIONS[this.data.profileRoleIndex]
      const years = TARGET_EXPERIENCE_YEARS[this.data.profileYearsIndex]
      if (role === undefined || years === undefined) {
        this.setData({
          profileError: "请选择目标岗位与经验年限",
          profileNotice: "",
        })
        return
      }

      this.setData({profileSaving: true, profileError: "", profileNotice: ""})
      try {
        const saved = await putDefaultTargetProfile({
          targetRole: role,
          relevantExperienceMonths: years * 12,
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
          profileFormOpen: false,
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
