/** Mirror Flutter SentimentAnalysis._parseRiskEvents — list APIs often store JSON strings. */

export function parseRiskEvents(raw) {
  if (raw == null) return []
  if (Array.isArray(raw)) {
    return raw.map((e) => String(e)).filter((e) => e.length > 0)
  }
  const text = String(raw).trim()
  if (!text) return []
  if (text.startsWith('[')) {
    try {
      const parsed = JSON.parse(text)
      if (Array.isArray(parsed)) {
        return parsed.map((e) => String(e)).filter((e) => e.length > 0)
      }
    } catch {
      /* fall through to split */
    }
  }
  return text
    .split(/[\n;；]/)
    .map((e) => e.trim())
    .filter((e) => e.length > 0)
}

/** Backend sentiment scores are about [-10, 10]; map to 0–100 like Flutter. */
export function sentimentIndexTo100(raw) {
  if (raw == null || raw === '') return null
  const n = Number(raw)
  if (!Number.isFinite(n)) return null
  if (n >= -10 && n <= 10) {
    return Math.min(100, Math.max(0, (n + 10) * 5))
  }
  return Math.min(100, Math.max(0, n))
}

export function sentimentDirection(raw) {
  const d = String(raw || '').toLowerCase()
  if (!d) return 'unknown'
  for (const token of ['多', 'bull', 'up', '涨', 'positive']) {
    if (d.includes(token)) return 'up'
  }
  for (const token of ['空', 'bear', 'down', '跌', 'negative']) {
    if (d.includes(token)) return 'down'
  }
  return 'flat'
}
