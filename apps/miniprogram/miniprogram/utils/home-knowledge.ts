import type {
  HomeLearningCard,
  HomeTopic,
} from "../fixtures/home-knowledge"

export interface HomeHeaderPresentation {
  dateLabel: string
  greeting: "早上好" | "下午好" | "晚上好"
}

type HomeClock = () => Date

const systemClock: HomeClock = () => new Date()
let homeClock: HomeClock = systemClock

export function formatHomeHeader(now: Date): HomeHeaderPresentation {
  const year = now.getFullYear()
  const month = padTwoDigits(now.getMonth() + 1)
  const day = padTwoDigits(now.getDate())
  const hour = now.getHours()

  return {
    dateLabel: `${year}.${month}.${day} · 今日训练`,
    greeting:
      hour >= 5 && hour < 12
        ? "早上好"
        : hour >= 12 && hour < 18
          ? "下午好"
          : "晚上好",
  }
}

export function currentHomeHeader(): HomeHeaderPresentation {
  return formatHomeHeader(homeClock())
}

export function setHomeClockForTests(clock: HomeClock | null): void {
  homeClock = clock ?? systemClock
}

export function formatTopicSummary(topic: HomeTopic): string {
  return `${topic.name} · ${topic.knowledgePointCount} 个知识点`
}

export function findHomeTopic(
  topics: HomeTopic[],
  topicId: string,
): HomeTopic | null {
  return topics.find((topic) => topic.id === topicId) ?? null
}

export function formatLearningProgress(card: HomeLearningCard): string {
  return `${padTwoDigits(card.currentStep)} / ${padTwoDigits(card.totalSteps)}`
}

function padTwoDigits(value: number): string {
  return String(value).padStart(2, "0")
}
