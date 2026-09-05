/** K-line period tabs and bar unwrap. Switching period only changes `period` on GET /market/kline. */

import { unwrapData, unwrapList, num, str } from './payload.js'

export const KLINE_PERIODS = [
  { key: 'intraday', label: '分时' },
  { key: 'daily', label: '日K' },
  { key: 'weekly', label: '周K' },
  { key: 'monthly', label: '月K' }
]

export function pickKlineBars(res) {
  const payload = unwrapData(res)
  return unwrapList({ data: payload }, ['klines', 'items', 'bars', 'list']).map((b) => ({
    date: str(b.date || b.time),
    open: num(b.open),
    high: num(b.high),
    low: num(b.low),
    close: num(b.close ?? b.last),
    volume: num(b.volume),
    turnover: num(b.turnover ?? b.amount)
  }))
}

export function isKlinePeriod(key) {
  return KLINE_PERIODS.some((p) => p.key === key)
}
