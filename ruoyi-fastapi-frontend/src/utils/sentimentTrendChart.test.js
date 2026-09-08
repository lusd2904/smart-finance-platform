import assert from 'node:assert/strict'
import { test } from 'node:test'

import { buildSentimentTrendOption, toTrendScore } from './sentimentTrendChart.js'

test('toTrendScore keeps 0 and maps missing values to null', () => {
  assert.equal(toTrendScore(0), 0)
  assert.equal(toTrendScore(70), 70)
  assert.equal(toTrendScore(null), null)
  assert.equal(toTrendScore(undefined), null)
  assert.equal(toTrendScore(''), null)
  assert.equal(toTrendScore('n/a'), null)
})

test('trend option connects nulls and does not 0-fill missing scores', () => {
  const option = buildSentimentTrendOption(
    [
      { createTime: '2026-09-03 07:10', usScore: 70, hkScore: 40, aScore: 20 },
      { createTime: '2026-09-03 07:20', usScore: null, hkScore: '', aScore: undefined },
      { createTime: '2026-09-03 07:28', usScore: 68, hkScore: 38, aScore: 22 }
    ],
    (value) => String(value)
  )

  assert.deepEqual(option.yAxis, { type: 'value', name: '分数', min: 0, max: 100 })
  assert.equal(option.series.length, 3)
  for (const series of option.series) {
    assert.equal(series.type, 'line')
    assert.equal(series.connectNulls, true)
    assert.ok(series.areaStyle)
    assert.equal(series.data[1], null)
    assert.notEqual(series.data[1], 0)
  }
  assert.deepEqual(option.series[0].data, [70, null, 68])
  assert.deepEqual(option.series[1].data, [40, null, 38])
  assert.deepEqual(option.series[2].data, [20, null, 22])
  assert.deepEqual(option.xAxis.data, [
    '2026-09-03 07:10',
    '2026-09-03 07:20',
    '2026-09-03 07:28'
  ])
})
