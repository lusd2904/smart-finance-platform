<template>
  <PageFrame title="财经资讯" :loading="loading">
    <template #actions>
      <el-radio-group v-model="market" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
        <el-radio-button value="CN">A股</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
      </el-radio-group>
      <el-input v-model="keyword" clearable placeholder="标题 / 摘要" style="width:200px" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <el-empty v-if="!loading && !filtered.length" description="暂无资讯" />
    <article v-for="item in filtered" :key="item.id || item.title" class="news-line glass-panel">
      <div>
        <el-tag size="small">{{ marketLabel(item.market) }}</el-tag>
        <strong>{{ item.title }}</strong>
      </div>
      <p>{{ item.summary || item.content || '' }}</p>
      <span class="muted">{{ item.source || '' }} {{ item.publishedAt || item.time || item.generatedAt || '' }}</span>
    </article>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getFinanceBriefings } from '@/api/market'
import { marketLabel, unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const market = ref('')
const keyword = ref('')
const list = ref([])

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  let arr = list.value
  if (market.value) arr = arr.filter((i) => i.market === market.value)
  if (kw) arr = arr.filter((i) => `${i.title} ${i.summary || ''}`.toLowerCase().includes(kw))
  return arr
})

async function load() {
  loading.value = true
  try {
    const res = await getFinanceBriefings({ market: market.value || undefined })
    const data = unwrap(res)
    list.value = data.items || data.briefings || unwrapList(res)
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.muted { color: var(--text-secondary); font-size: 12px; }
.news-line p { margin: 0; color: var(--text-primary); }
.news-line strong { margin-left: 8px; }
</style>
