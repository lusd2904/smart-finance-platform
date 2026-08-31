<template>
  <div class="app-container">
    <el-card shadow="never" class="guide-card">
      <template #header>
        <span class="guide-title">使用说明</span>
      </template>
      <el-skeleton v-if="loading" :rows="8" animated />
      <el-alert
        v-else-if="error"
        title="加载失败"
        type="error"
        show-icon
        :closable="false"
      />
      <article v-else class="guide-article">
        <GuideMarkdown :source="markdown" />
      </article>
    </el-card>
  </div>
</template>

<script setup name="GuideIndex">
import { ElMessage } from 'element-plus'
import { getGuide } from '@/api/guide'

const GUIDE_MODULES = ['market', 'quant', 'trade', 'sentiment', 'ai', 'analysis']

const route = useRoute()
const loading = ref(true)
const error = ref(false)
const markdown = ref('')
let fetchSeq = 0

const guideModule = computed(() => {
  const seg = String(route.path || '').split('/').filter(Boolean)[0] || ''
  if (GUIDE_MODULES.includes(seg)) return seg
  const raw = route.query && route.query.module
  const value = Array.isArray(raw) ? raw[0] : raw
  return String(value || '').trim()
})

function extractMarkdown(res) {
  if (res == null) return ''
  if (typeof res === 'string') return res
  const data = res.data
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    for (const key of ['content', 'markdown', 'text', 'guide']) {
      if (typeof data[key] === 'string') return data[key]
    }
  }
  for (const key of ['content', 'markdown', 'text', 'guide']) {
    if (typeof res[key] === 'string') return res[key]
  }
  return ''
}

function parseInline(text) {
  const src = String(text || '')
  const parts = []
  const re = /\*\*(.+?)\*\*|`([^`]+)`/g
  let last = 0
  let match
  while ((match = re.exec(src))) {
    if (match.index > last) {
      parts.push({ type: 'text', text: src.slice(last, match.index) })
    }
    if (match[1] != null) {
      parts.push({ type: 'bold', text: match[1] })
    } else {
      parts.push({ type: 'code', text: match[2] })
    }
    last = match.index + match[0].length
  }
  if (last < src.length) {
    parts.push({ type: 'text', text: src.slice(last) })
  }
  return parts
}

function renderInline(parts) {
  return parts.map((part, idx) => {
    if (part.type === 'bold') return h('strong', { key: idx }, part.text)
    if (part.type === 'code') return h('code', { key: idx }, part.text)
    return part.text
  })
}

function isHeading(line) {
  return /^(#{1,3})\s+/.test(line)
}

function isUl(line) {
  return /^-\s+/.test(line)
}

function isOl(line) {
  return /^\d+\.\s+/.test(line)
}

function parseAndRender(source) {
  const lines = String(source || '').replace(/\r\n/g, '\n').split('\n')
  const nodes = []
  let i = 0
  let key = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i += 1
      continue
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line)
    if (heading) {
      nodes.push(h('h' + heading[1].length, { key: key++ }, renderInline(parseInline(heading[2]))))
      i += 1
      continue
    }
    if (isUl(line)) {
      const items = []
      while (i < lines.length && isUl(lines[i])) {
        items.push(h('li', { key: items.length }, renderInline(parseInline(lines[i].replace(/^-\s+/, '')))))
        i += 1
      }
      nodes.push(h('ul', { key: key++ }, items))
      continue
    }
    if (isOl(line)) {
      const items = []
      while (i < lines.length && isOl(lines[i])) {
        items.push(h('li', { key: items.length }, renderInline(parseInline(lines[i].replace(/^\d+\.\s+/, '')))))
        i += 1
      }
      nodes.push(h('ol', { key: key++ }, items))
      continue
    }
    const buf = []
    while (i < lines.length && lines[i].trim() && !isHeading(lines[i]) && !isUl(lines[i]) && !isOl(lines[i])) {
      buf.push(lines[i].trim())
      i += 1
    }
    nodes.push(h('p', { key: key++ }, renderInline(parseInline(buf.join(' ')))))
  }
  return nodes
}

const GuideMarkdown = defineComponent({
  name: 'GuideMarkdown',
  props: {
    source: { type: String, default: '' }
  },
  setup(props) {
    return () => h('div', { class: 'guide-body' }, parseAndRender(props.source))
  }
})

function failLoad() {
  error.value = true
  markdown.value = ''
  ElMessage.error('加载失败')
}

async function loadGuide(mod) {
  const seq = ++fetchSeq
  loading.value = true
  error.value = false
  markdown.value = ''
  if (!mod || !/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(mod)) {
    loading.value = false
    failLoad()
    return
  }
  try {
    const res = await getGuide(mod)
    if (seq !== fetchSeq) return
    markdown.value = extractMarkdown(res)
  } catch (_e) {
    if (seq !== fetchSeq) return
    failLoad()
  } finally {
    if (seq === fetchSeq) loading.value = false
  }
}

watch(guideModule, (mod) => {
  loadGuide(mod)
}, { immediate: true })
</script>

<style scoped lang="scss">
.guide-title {
  font-weight: 600;
  color: var(--text-emphasis, var(--el-text-color-primary));
}

.guide-article {
  color: var(--text-emphasis, var(--el-text-color-primary));
  font-size: 14px;
  line-height: 1.75;
  word-break: break-word;

  :deep(.guide-body) {
    h1, h2, h3 {
      color: var(--text-emphasis, var(--el-text-color-primary));
      font-weight: 600;
      line-height: 1.35;
    }

    h1 {
      font-size: 22px;
      margin: 0 0 12px;
    }

    h2 {
      font-size: 18px;
      margin: 20px 0 10px;
    }

    h3 {
      font-size: 16px;
      margin: 16px 0 8px;
    }

    p {
      margin: 0 0 10px;
      color: var(--text-secondary, var(--el-text-color-regular));
    }

    ul, ol {
      margin: 0 0 12px;
      padding-left: 1.4em;
      color: var(--text-secondary, var(--el-text-color-regular));
    }

    li {
      margin: 4px 0;
    }

    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 85%;
      padding: 0.15em 0.4em;
      border-radius: 4px;
      background: var(--surface-muted, var(--el-fill-color-light));
      color: var(--text-emphasis, var(--el-text-color-primary));
    }

    strong {
      color: var(--text-emphasis, var(--el-text-color-primary));
      font-weight: 600;
    }
  }
}
</style>
