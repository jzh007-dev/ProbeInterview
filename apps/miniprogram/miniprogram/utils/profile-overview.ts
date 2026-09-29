export function formatExperience(months: number): string {
  if (months < 12) {
    return `${months} 个月`
  }
  const years = Math.floor(months / 12)
  const remainingMonths = months % 12
  if (remainingMonths === 0) {
    return `${years} 年`
  }
  return `${years} 年 ${remainingMonths} 个月`
}

export function avatarInitials(nickname: string): string {
  const normalized = nickname.trim()
  if (!normalized) {
    return "?"
  }
  const words = normalized.split(/\s+/)
  if (words.length > 1) {
    return words
      .slice(0, 2)
      .map((word) => Array.from(word)[0] ?? "")
      .join("")
      .toUpperCase()
  }
  return Array.from(normalized).slice(0, 2).join("").toUpperCase()
}
