/** Mask secrets for UI. Never log or toast the raw value. */
export function maskSecret(value) {
  const text = String(value || '')
  if (!text) return ''
  if (text.startsWith('****')) return text
  return text.length > 4 ? `****${text.slice(-4)}` : '****'
}

export function isMaskedSecret(value) {
  const text = String(value || '')
  return !text || text.startsWith('****')
}

export function looksLikeSecret(value) {
  const text = String(value || '')
  return /(?:sk-|lb-|app[_-]?key|app[_-]?secret|access[_-]?token|api[_-]?key)/i.test(text)
}

/** Strip credential-looking fragments from error / toast copy. */
export function sanitizePublicText(value, fallback = '操作失败') {
  const text = String(value || '').trim()
  if (!text) return fallback
  const cleaned = text
    .replace(/(?:sk-|lb-)[A-Za-z0-9._-]{6,}/g, '[redacted]')
    .replace(/(?:app[_-]?key|app[_-]?secret|access[_-]?token|api[_-]?key)\s*[:=]\s*\S+/gi, '[redacted]')
  if (looksLikeSecret(cleaned)) return fallback
  return cleaned
}
