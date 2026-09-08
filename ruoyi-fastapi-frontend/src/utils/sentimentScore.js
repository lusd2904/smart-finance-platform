/**
 * 与 Flutter `sentimentIndexTo100` / 后端 normalize_sentiment_score 一致。
 * |x|≤10 视为历史 ±10 制：(x+10)*5；已是 0–100 则夹紧。
 */
export function sentimentIndexTo100(raw) {
  if (raw === null || raw === undefined || raw === '') {
    return null
  }
  const value = Number(raw)
  if (!Number.isFinite(value)) {
    return null
  }
  if (value >= -10 && value <= 10) {
    return Math.min(100, Math.max(0, (value + 10) * 5))
  }
  return Math.min(100, Math.max(0, value))
}
