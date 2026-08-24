const assert = require('assert')
const { normalizeGateway, probeGateway } = require('./gateway')
const { mustConfigureGateway } = require('./main-boot')

// 无协议地址默认按 https 处理（不再静默降级 http）；显式 http:// 保留
assert.equal(normalizeGateway('127.0.0.1:12580'), 'https://127.0.0.1:12580')
assert.equal(normalizeGateway('http://127.0.0.1:12580/'), 'http://127.0.0.1:12580')
assert.equal(normalizeGateway('https://fin.example.com/login'), 'https://fin.example.com')
assert.throws(() => normalizeGateway('file:///tmp'), /仅支持/)
assert.equal(mustConfigureGateway(), true)

async function main() {
  const frontend = await probeGateway('http://127.0.0.1:12580')
  assert.equal(frontend.ok, true, frontend.message)
  const backend = await probeGateway('http://127.0.0.1:19099')
  assert.equal(backend.ok, false)
  assert.match(backend.message, /后端 API|前端网关/)
  console.log('gateway tests ok', frontend.message)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
