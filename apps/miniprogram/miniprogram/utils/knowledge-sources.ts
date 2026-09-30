import type {
  KnowledgeSourceItem,
  KnowledgeSourceQuota,
} from "../services/knowledge-sources"

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KiB`
}

export function formatUploadTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ""
  }
  const twoDigits = (number: number) => number.toString().padStart(2, "0")
  return `${twoDigits(date.getMonth() + 1)}-${twoDigits(date.getDate())} ${twoDigits(date.getHours())}:${twoDigits(date.getMinutes())}`
}

export function sortNewestFirst(
  items: KnowledgeSourceItem[],
): KnowledgeSourceItem[] {
  return [...items].sort((left, right) => {
    const timeOrder =
      new Date(right.uploaded_at).getTime() - new Date(left.uploaded_at).getTime()
    return timeOrder || right.id.localeCompare(left.id)
  })
}

export function quotaExhausted(quota: KnowledgeSourceQuota): boolean {
  return (
    quota.daily_used >= quota.daily_limit ||
    quota.effective_source_count >= quota.effective_source_limit
  )
}

export function createIdempotencyKey(): string {
  return `knowledge-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}
