import {HOME_KNOWLEDGE_FIXTURE} from "../../fixtures/home-knowledge"
import {
  readCurrentUserSnapshot,
  type CurrentUserSnapshot,
} from "../../services/current-user-store"
import {
  currentHomeHeader,
  findHomeTopic,
  formatLearningProgress,
  formatTopicSummary,
} from "../../utils/home-knowledge"

export const HOME_ACTIONS = [
  "search-knowledge",
  "continue-learning",
  "select-topic",
] as const

export type HomeAction = (typeof HOME_ACTIONS)[number]

const LOGIN_PAGE_PATH = "/pages/login/index"
const PROFILE_TAB_URL = "/pages/profile/index"

type HomeViewStatus = "loading" | "success"

const initialLearningCard = HOME_KNOWLEDGE_FIXTURE.learningCards[0]
const initialTopic =
  findHomeTopic(
    HOME_KNOWLEDGE_FIXTURE.topics,
    HOME_KNOWLEDGE_FIXTURE.initialSelectedTopicId,
  ) ?? HOME_KNOWLEDGE_FIXTURE.topics[0]

if (initialLearningCard === undefined || initialTopic === undefined) {
  throw new Error("Home knowledge fixture must include cards and topics.")
}

interface HomeKnowledgeOverviewData {
  status: HomeViewStatus
  currentUser: CurrentUserSnapshot | null
  dateLabel: string
  greeting: string
  weeklyCoveragePercent: number
  coveredTopicCount: number
  pendingReviewCount: number
  learningCards: typeof HOME_KNOWLEDGE_FIXTURE.learningCards
  topics: typeof HOME_KNOWLEDGE_FIXTURE.topics
  currentLearningIndex: number
  currentLearningProgress: string
  selectedTopicId: string
  selectedTopicSummary: string
  lastAction: HomeAction | ""
}

const INITIAL_DATA: HomeKnowledgeOverviewData = {
  status: "loading",
  currentUser: null,
  dateLabel: "",
  greeting: "",
  weeklyCoveragePercent: HOME_KNOWLEDGE_FIXTURE.weeklyCoveragePercent,
  coveredTopicCount: HOME_KNOWLEDGE_FIXTURE.coveredTopicCount,
  pendingReviewCount: HOME_KNOWLEDGE_FIXTURE.pendingReviewCount,
  learningCards: HOME_KNOWLEDGE_FIXTURE.learningCards,
  topics: HOME_KNOWLEDGE_FIXTURE.topics,
  currentLearningIndex: 0,
  currentLearningProgress: formatLearningProgress(initialLearningCard),
  selectedTopicId: initialTopic.id,
  selectedTopicSummary: formatTopicSummary(initialTopic),
  lastAction: "",
}

Component({
  data: INITIAL_DATA,

  lifetimes: {
    attached() {
      this.refreshHeader()
      this.syncCurrentUser()
    },
  },

  pageLifetimes: {
    show() {
      this.refreshHeader()
      this.syncCurrentUser()
    },
  },

  methods: {
    refreshHeader() {
      this.setData(currentHomeHeader())
    },

    syncCurrentUser() {
      const snapshot = readCurrentUserSnapshot()
      if (snapshot === null) {
        this.setData({status: "loading", currentUser: null})
        wx.reLaunch({url: LOGIN_PAGE_PATH})
        return
      }
      this.setData({status: "success", currentUser: snapshot})
    },

    onGoToProfile() {
      wx.switchTab({url: PROFILE_TAB_URL})
    },

    onSwiperChange(event: {detail: {current?: unknown}}) {
      const current = event.detail.current
      if (
        typeof current !== "number" ||
        !Number.isInteger(current) ||
        current < 0 ||
        current >= this.data.learningCards.length
      ) {
        return
      }

      const card = this.data.learningCards[current]
      if (card === undefined) {
        return
      }
      this.setData({
        currentLearningIndex: current,
        currentLearningProgress: formatLearningProgress(card),
      })
    },

    onSelectTopic(
      event: WechatMiniprogram.CustomEvent<
        Record<string, never>,
        Record<string, never>,
        {topicId?: unknown}
      >,
    ) {
      const topicId = event.currentTarget.dataset.topicId
      if (typeof topicId !== "string") {
        return
      }
      const topic = findHomeTopic(this.data.topics, topicId)
      if (topic === null) {
        return
      }
      this.setData({
        selectedTopicId: topic.id,
        selectedTopicSummary: formatTopicSummary(topic),
        lastAction: "select-topic",
      })
    },

    handleAction(
      event: WechatMiniprogram.CustomEvent<
        Record<string, never>,
        Record<string, never>,
        {action?: unknown}
      >,
    ) {
      const action = event.currentTarget.dataset.action
      if (action !== "search-knowledge" && action !== "continue-learning") {
        return
      }
      this.setData({lastAction: action})
    },
  },
})
