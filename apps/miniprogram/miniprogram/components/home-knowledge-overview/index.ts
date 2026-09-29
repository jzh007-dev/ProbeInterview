import {HOME_KNOWLEDGE_FIXTURE} from "../../fixtures/home-knowledge"
import {
  currentUserSnapshotFromOverview,
  readCurrentUserSnapshot,
  writeCurrentUserSnapshot,
  type CurrentUserSnapshot,
} from "../../services/current-user-store"
import {fetchProfileOverview} from "../../services/profile-overview"
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
type HomeViewStatus = "loading" | "success" | "error"

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
  errorMessage: string
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
  errorMessage: "",
  lastAction: "",
}

Component({
  data: INITIAL_DATA,

  lifetimes: {
    attached() {
      this.refreshHeader()
      void this.loadCurrentUser()
    },
  },

  pageLifetimes: {
    show() {
      this.refreshHeader()
    },
  },

  methods: {
    refreshHeader() {
      this.setData(currentHomeHeader())
    },

    async loadCurrentUser() {
      this.setData({
        status: "loading",
        currentUser: null,
        errorMessage: "",
      })

      const cachedUser = readCurrentUserSnapshot()
      if (cachedUser !== null) {
        this.setData({
          status: "success",
          currentUser: cachedUser,
        })
        return
      }

      try {
        const overview = await fetchProfileOverview()
        const currentUser = writeCurrentUserSnapshot(
          currentUserSnapshotFromOverview(overview),
        )
        this.setData({
          status: "success",
          currentUser,
        })
      } catch {
        this.setData({
          status: "error",
          currentUser: null,
          errorMessage: "首页身份信息加载失败，请稍后重试",
        })
      }
    },

    onRetry() {
      void this.loadCurrentUser()
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
