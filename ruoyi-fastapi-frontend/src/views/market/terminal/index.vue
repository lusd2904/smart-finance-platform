<template>
  <div class="app-container pro-terminal-page" :class="{ 'is-fullscreen': isFullscreen }">
    <!-- 顶部状态栏：左侧开盘大盘指数，右侧搜索、资金与操作 -->
    <div class="terminal-topbar">
      <!-- 动态大盘指数区：美股全时段显示（夜盘/盘前/盘中/盘后），港股A股开盘时显示 -->
      <div class="topbar-indices-wrap">
        <div
          v-for="idx in activeMarketIndices"
          :key="idx.symbol"
          class="index-card-chip"
          :class="idx.changeRate >= 0 ? 'up' : 'down'"
          :title="`${idx.name} (${idx.symbol}) · ${idx.sessionStatus.label}`"
        >
          <span class="mkt-session-badge" :class="idx.sessionStatus.sessionTag">
            {{ idx.sessionStatus.sessionName }}
          </span>
          <span class="idx-name">{{ idx.name }}</span>
          <span class="idx-price">{{ Number(idx.price || 0).toFixed(2) }}</span>
          <span class="idx-change">
            {{ idx.changeRate >= 0 ? '+' : '' }}{{ Number(idx.changeRate || 0).toFixed(2) }}%
          </span>
        </div>
      </div>

      <!-- 右侧自适应工具栏：搜索框、可用资金胶囊与功能按钮 -->
      <div class="topbar-right-controls">
        <el-autocomplete
          v-model="searchKeyword"
          :fetch-suggestions="querySearchStocks"
          value-key="symbol"
          placeholder="搜索全市场代码 / 名称"
          size="small"
          class="top-search-box"
          :prefix-icon="Search"
          clearable
          @select="handleSearchSelect"
        >
          <template #default="{ item }">
            <div class="search-item-line">
              <span class="s-sym">{{ item.symbol }}</span>
              <span class="s-nm">{{ item.name }}</span>
              <el-tag size="small" effect="plain" class="s-mkt">{{ item.market }}</el-tag>
            </div>
          </template>
        </el-autocomplete>

        <!-- 资金胶囊 (严格单行不换行) -->
        <div class="cash-stat-capsule">
          <span class="cash-label">可用资金</span>
          <span class="cash-amount">{{ cashCurrency }} {{ Number(accountCash || 0).toLocaleString('en-US', { minimumFractionDigits: 2 }) }}</span>
        </div>

        <el-tooltip
          :content="autoTradeConfigured ? (autoTradeEnabled ? '自动交易已开启' : '打开自动交易') : '未配置长桥 Key，无法打开自动交易'"
          placement="bottom"
        >
          <div class="auto-trade-switch" :class="{ disabled: !autoTradeConfigured }">
            <span class="auto-trade-label">量化</span>
            <el-switch
              :model-value="autoTradeEnabled"
              :disabled="!autoTradeConfigured || autoTradeSaving"
              :loading="autoTradeSaving"
              size="small"
              @change="onToggleAutoTrade"
            />
          </div>
        </el-tooltip>
        <span class="live-flag" :class="liveMode ? 'on' : 'off'">{{ liveMode ? 'LIVE' : 'SIM' }}</span>
        <el-tooltip :content="liveMode ? '刷新真实行情' : '重置行情模拟波动'" placement="bottom">
          <el-button circle size="small" :icon="Refresh" @click="resetSimulation" />
        </el-tooltip>
        <el-tooltip :content="isFullscreen ? '退出全屏' : '全屏盯盘模式'" placement="bottom">
          <el-button circle size="small" :icon="FullScreen" @click="toggleFullscreen" />
        </el-tooltip>
      </div>
    </div>

    <!-- 终端主三栏布局 -->
    <div class="terminal-main-grid">
      <!-- ====================== 左侧：自选清单面板 ====================== -->
      <aside class="panel-card left-pane">
        <div class="panel-head">
          <div class="head-left">
            <el-icon class="star-icon"><StarFilled /></el-icon>
            <span class="head-title">自选清单</span>
            <span class="count-badge">{{ filteredStocks.length }}</span>
          </div>
          <el-dropdown trigger="click" @command="handleGroupChange">
            <span class="group-select-btn">
              {{ currentGroup }} <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="g in watchGroupNames" :key="g" :command="g">{{ g === '全部' ? '全部自选' : g }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <!-- 过滤与多维排序 -->
        <div class="watchlist-toolbar">
          <el-input
            v-model="watchFilterKw"
            placeholder="过滤代码/名称..."
            size="small"
            clearable
            :prefix-icon="Search"
            class="watch-filter-input"
          />
          <div class="sort-actions-bar">
            <span
              class="sort-tab"
              :class="{ active: sortField === 'changeRate' }"
              @click="toggleSort('changeRate')"
            >
              涨跌幅 <i :class="sortOrder === 'desc' && sortField === 'changeRate' ? 'el-icon-caret-bottom' : 'el-icon-caret-top'" />
            </span>
            <span
              class="sort-tab"
              :class="{ active: sortField === 'price' }"
              @click="toggleSort('price')"
            >
              现价
            </span>
            <span
              class="sort-tab"
              :class="{ active: sortField === 'turnover' }"
              @click="toggleSort('turnover')"
            >
              成交额
            </span>
          </div>
        </div>

        <!-- 自选标的列表 -->
        <div class="watchlist-body">
          <div
            v-for="item in sortedWatchStocks"
            :key="item.symbol + '.' + item.market"
            class="stock-row-card"
            :class="{ active: activeSymbol === item.symbol }"
            @click="selectStock(item)"
          >
            <div class="stock-info">
              <div class="sym-line">
                <span class="stock-code">{{ item.symbol }}</span>
                <span class="market-badge" :class="item.market.toLowerCase()">{{ item.market }}</span>
              </div>
              <div class="stock-name">{{ item.name }}</div>
            </div>

            <!-- 微型 Sparkline 走势图 -->
            <div class="sparkline-box">
              <svg viewBox="0 0 60 22" class="spark-svg">
                <path
                  :d="renderSparklinePath(item.sparkline)"
                  fill="none"
                  :stroke="item.changeRate >= 0 ? 'var(--stat-up, #dc2626)' : 'var(--stat-down, #059669)'"
                  stroke-width="1.6"
                  stroke-linecap="round"
                />
              </svg>
            </div>

            <div class="price-info">
              <div class="price-val" :class="getPriceFlashClass(item.symbol)">
                {{ fmtPx(item.price) }}
              </div>
              <div class="change-pill" :class="item.price ? (item.changeRate >= 0 ? 'up' : 'down') : ''">
                {{ item.price ? fmtSigned(item.changeRate) + '%' : '--' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 底部组合涨跌统计 -->
        <div class="watchlist-footer">
          <div class="footer-stat-line">
            <span class="lbl">自选组合今日走势</span>
            <span class="val" :class="watchStats.avg >= 0 ? 'up' : 'down'">{{ fmtSigned(watchStats.avg) }}%</span>
          </div>
          <div class="stat-progress-bar">
            <div class="bar-segment up-seg" :style="{ width: watchStats.upPct + '%' }"></div>
            <div class="bar-segment down-seg" :style="{ width: watchStats.downPct + '%' }"></div>
          </div>
          <div class="stat-sub-info">
            <span class="up">● 上涨 {{ watchStats.up }}</span>
            <span class="flat">● 平盘 {{ watchStats.flat }}</span>
            <span class="down">● 下跌 {{ watchStats.down }}</span>
          </div>
        </div>
      </aside>

      <!-- ====================== 中间：深度行情图表与多维分析 ====================== -->
      <section class="panel-card center-pane">
        <!-- 标的大字行情看板 -->
        <div class="ticker-board-card">
          <div class="ticker-top-row">
            <div class="ticker-meta-block">
              <div class="name-line">
                <span class="big-symbol">{{ activeStock.symbol }}</span>
                <span class="full-name">{{ activeStock.name }}</span>
                <el-tag v-if="activeStock.category" size="small" effect="plain" class="category-tag">{{ activeStock.category }}</el-tag>
                <el-tag size="small" type="warning" effect="dark" class="ai-score-pill">
                  AI 研判 {{ activeStock.aiScore != null ? activeStock.aiScore + '分' : '--' }}
                </el-tag>
              </div>
              <div class="sub-meta-line">
                <span>市场: {{ activeStock.market }} ({{ activeStock.currency }})</span>
                <span class="split-dot">·</span>
                <span class="status-live">● {{ activeSession.label }}</span>
              </div>
            </div>

            <!-- 超大实时价格看板 (带跳动闪烁) -->
            <div class="ticker-price-block" :class="heroPriceClass">
              <div class="main-price-num">
                {{ fmtNum(activeStock.price, 3) }}
                <span class="currency-unit">{{ activeStock.currency }}</span>
              </div>
              <div class="chg-rate-line">
                <span class="chg-num">{{ fmtSigned(activeStock.change, 3) }}</span>
                <span class="chg-pct">({{ fmtSigned(activeStock.changeRate) }}%)</span>
              </div>
            </div>
          </div>

          <!-- 紧凑指标矩阵 (12 项) -->
          <div class="quote-metrics-grid">
            <div class="q-cell"><span class="q-lbl">今开</span><span class="q-val" :class="activeStock.open >= activeStock.prevClose ? 'up' : 'down'">{{ fmtNum(activeStock.open, 3) }}</span></div>
            <div class="q-cell"><span class="q-lbl">最高</span><span class="q-val up">{{ fmtNum(activeStock.high, 3) }}</span></div>
            <div class="q-cell"><span class="q-lbl">最低</span><span class="q-val down">{{ fmtNum(activeStock.low, 3) }}</span></div>
            <div class="q-cell"><span class="q-lbl">昨收</span><span class="q-val">{{ fmtNum(activeStock.prevClose, 3) }}</span></div>
            <div class="q-cell"><span class="q-lbl">成交量</span><span class="q-val">{{ formatVolume(activeStock.volume) }}</span></div>
            <div class="q-cell"><span class="q-lbl">成交额</span><span class="q-val">{{ formatTurnover(activeStock.turnover) }}</span></div>
            <div class="q-cell"><span class="q-lbl">换手率</span><span class="q-val">{{ dash(activeStock.turnoverRate) }}</span></div>
            <div class="q-cell"><span class="q-lbl">振幅</span><span class="q-val">{{ dash(activeStock.amplitude) }}</span></div>
            <div class="q-cell"><span class="q-lbl">量比</span><span class="q-val">{{ dash(activeStock.volumeRatio) }}</span></div>
            <div class="q-cell"><span class="q-lbl">市盈率(TTM)</span><span class="q-val">{{ dash(activeStock.peTTM || activeStock.pe) }}</span></div>
            <div class="q-cell"><span class="q-lbl">市净率 PB</span><span class="q-val">{{ dash(activeStock.pb) }}</span></div>
            <div class="q-cell"><span class="q-lbl">总市值</span><span class="q-val">{{ dash(activeStock.marketCap) }}</span></div>
          </div>
        </div>

        <!-- 图表控制栏 -->
        <div class="chart-action-bar">
          <div class="period-button-group">
            <button
              v-for="p in periodOptions"
              :key="p.value"
              class="period-toggle-btn"
              :class="{ active: currentPeriod === p.value }"
              @click="setPeriod(p.value)"
            >
              {{ p.label }}
            </button>
          </div>

          <div class="indicator-group-wrap">
            <span class="ind-lbl">主图:</span>
            <el-checkbox-group v-model="mainIndicators" size="small" @change="renderECharts">
              <el-checkbox-button value="MA">MA均线</el-checkbox-button>
              <el-checkbox-button value="EMA">EMA</el-checkbox-button>
              <el-checkbox-button value="BOLL">BOLL</el-checkbox-button>
            </el-checkbox-group>

            <span class="ind-lbl" style="margin-left: 12px">副图:</span>
            <el-radio-group v-model="subIndicator" size="small" @change="renderECharts">
              <el-radio-button value="VOL">VOL量</el-radio-button>
              <el-radio-button value="MACD">MACD</el-radio-button>
              <el-radio-button value="KDJ">KDJ</el-radio-button>
              <el-radio-button value="RSI">RSI</el-radio-button>
              <el-radio-button value="FLOW">资金流向</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <!-- 专业级 ECharts 图表主画板 -->
        <div class="chart-canvas-container">
          <div ref="chartContainerRef" class="echarts-inner-dom"></div>
        </div>

        <!-- 底部多维投研分析抽屉 -->
        <div class="center-bottom-drawer">
          <el-tabs v-model="activeBottomTab" class="sub-analysis-tabs">
            <!-- Tab 1: AI 智能研判 -->
            <el-tab-pane name="ai">
              <template #label>
                <span class="tab-pill-label"><el-icon><MagicStick /></el-icon> AI 智能研判 (Grok 4.6)</span>
              </template>
              <div class="tab-pane-ai">
                <div class="ai-summary-header">
                  <span class="verdict-badge" :class="activeStock.aiScore >= 85 ? 'bull' : 'neutral'">
                    {{ activeStock.aiVerdict }}
                  </span>
                  <span class="conf-text">模型综合置信度: <strong>{{ activeStock.aiScore != null ? fmtNum(activeStock.aiScore, 1) + '%' : '--' }}</strong></span>
                </div>
                <div class="ai-opinion-box">
                  <p>{{ activeStock.aiSummary || '暂无该标的 AI 研判，请到 AI 研判工作台生成。' }}</p>
                </div>
                <div class="factor-chips-row">
                  <div v-for="f in activeStock.factors" :key="f.name" class="factor-score-chip">
                    <span class="f-lbl">{{ f.name }}</span>
                    <span class="f-val" :class="f.score >= 80 ? 'up' : ''">{{ f.score }}分</span>
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <!-- Tab 2: 实时快讯舆情 -->
            <el-tab-pane name="news">
              <template #label>
                <span class="tab-pill-label"><el-icon><Document /></el-icon> 标的快讯与舆情</span>
              </template>
              <div class="tab-pane-news">
                <div v-if="!(activeStock.news && activeStock.news.length)" class="empty-hint-text">暂无该标的快讯</div>
                <div v-for="item in activeStock.news" :key="item.id" class="news-item-line">
                  <span class="sentiment-pill" :class="item.sentiment">
                    {{ item.sentiment === 'bull' ? '利多' : item.sentiment === 'bear' ? '利空' : '中性' }}
                  </span>
                  <span class="news-txt">{{ item.title }}</span>
                  <span class="news-src">{{ item.source }}</span>
                  <span class="news-time">{{ item.time }}</span>
                </div>
              </div>
            </el-tab-pane>

            <!-- Tab 3: 主力资金博弈 -->
            <el-tab-pane name="flow">
              <template #label>
                <span class="tab-pill-label"><el-icon><PieChart /></el-icon> 资金大单博弈</span>
              </template>
              <div class="tab-pane-flow">
                <div v-if="!hasCapitalFlow" class="empty-hint-text">暂无资金流向数据</div>
                <div v-else class="flow-cards-grid">
                  <div class="flow-stat-cell">
                    <span class="flow-lbl">超大单净流入</span>
                    <span class="flow-val up">+{{ activeStock.capitalFlow.superIn - activeStock.capitalFlow.superOut }} 万</span>
                  </div>
                  <div class="flow-stat-cell">
                    <span class="flow-lbl">大单净流入</span>
                    <span class="flow-val up">+{{ activeStock.capitalFlow.largeIn - activeStock.capitalFlow.largeOut }} 万</span>
                  </div>
                  <div class="flow-stat-cell">
                    <span class="flow-lbl">中单净流入</span>
                    <span class="flow-val down">{{ activeStock.capitalFlow.midIn - activeStock.capitalFlow.midOut }} 万</span>
                  </div>
                  <div class="flow-stat-cell highlight">
                    <span class="flow-lbl">当日主力净额</span>
                    <span class="flow-val up font-bold">+{{ activeStock.capitalFlow.netInflow }} 万</span>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </section>

      <!-- ====================== 右侧：流式垂直容器 (高度滑动仅限制在右侧一栏) ====================== -->
      <aside class="right-pane">
        <!-- 1. 顶部 Tab 模块：基本信息 / 盘口 / 逐笔 -->
        <div class="depth-stream-card">
          <el-tabs v-model="rightTopTab" class="tight-tabs">
            <!-- 1.1 基本信息 Tab (默认打开，指标自然展示，无内部滚动条) -->
            <el-tab-pane label="基本信息" name="info">
              <div class="stock-full-info-view">
                <!-- 标的抬头与收藏/提醒 -->
                <div class="info-top-header">
                  <div class="info-symbol-title">
                    <span class="code">{{ activeStock.symbol }}</span>
                    <span class="name">{{ activeStock.name }}</span>
                  </div>
                  <div class="info-header-acts">
                    <el-icon class="act-heart" :class="{ favorited: isFavorited }" @click="toggleFavorite"><StarFilled /></el-icon>
                    <el-icon class="act-bell"><Bell /></el-icon>
                  </div>
                </div>

                <!-- 报价大字看板 (像素级还原) -->
                <div class="info-hero-price-box" :class="activeStock.changeRate >= 0 ? 'up' : 'down'">
                  <span class="price-main-num">{{ fmtPx(activeStock.price, 3) }}</span>
                  <span class="price-arrow">{{ activeStock.changeRate >= 0 ? '↑' : '↓' }}</span>
                  <span class="price-chg-val">{{ fmtSigned(activeStock.change, 3) }}</span>
                  <span class="price-chg-pct">{{ fmtSigned(activeStock.changeRate) }}%</span>
                </div>

                <!-- 时段状态与特色业务胶囊 -->
                <div class="info-status-badges-row">
                  <span class="quote-time-text">{{ toBeijingDisplay(activeStock.quoteTime) || activeSession.label }}</span>
                  <div class="biz-badges-group">
                    <span class="biz-badge flag">{{ activeStock.market === 'US' ? '🇺🇸' : activeStock.market === 'HK' ? '🇭🇰' : '🇨🇳' }}</span>
                    <span class="biz-badge l2">⚡2</span>
                    <span class="biz-badge all24">24</span>
                    <span class="biz-badge margin">融</span>
                    <span class="biz-badge opt">期</span>
                    <span class="biz-badge short">沽</span>
                  </div>
                </div>

                <!-- 核心双列指标网格 (前3行常驻展示) -->
                <div class="info-detailed-metrics-grid">
                  <div class="m-row">
                    <div class="m-cell"><span class="m-lbl">最高</span><span class="m-val up">{{ fmtPx(activeStock.high, 3) }}</span></div>
                    <div class="m-cell"><span class="m-lbl">最低</span><span class="m-val down">{{ fmtPx(activeStock.low, 3) }}</span></div>
                  </div>
                  <div class="m-row">
                    <div class="m-cell"><span class="m-lbl">今开</span><span class="m-val" :class="activeStock.open >= activeStock.prevClose ? 'up' : 'down'">{{ fmtPx(activeStock.open, 3) }}</span></div>
                    <div class="m-cell"><span class="m-lbl">昨收</span><span class="m-val">{{ fmtPx(activeStock.prevClose, 3) }}</span></div>
                  </div>
                  <div class="m-row">
                    <div class="m-cell"><span class="m-lbl">成交量</span><span class="m-val">{{ activeStock.volumeText || formatVolume(activeStock.volume) }}</span></div>
                    <div class="m-cell"><span class="m-lbl">成交额</span><span class="m-val">{{ activeStock.turnoverText || formatTurnover(activeStock.turnover) }}</span></div>
                  </div>

                  <!-- 点击展开时在当前页面自然展开 (共11行) -->
                  <template v-if="isInfoExpanded">
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">市值 ⓘ</span><span class="m-val">{{ activeStock.marketCap }}</span></div>
                      <div class="m-cell"><span class="m-lbl">总股本</span><span class="m-val">{{ activeStock.totalShares }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">流通值</span><span class="m-val">{{ activeStock.floatMarketCap }}</span></div>
                      <div class="m-cell"><span class="m-lbl">流通股</span><span class="m-val">{{ activeStock.floatShares }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">市盈率TTM</span><span class="m-val">{{ activeStock.peTTM }}</span></div>
                      <div class="m-cell"><span class="m-lbl">市盈率(静)</span><span class="m-val">{{ activeStock.peStatic }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">市净率</span><span class="m-val">{{ activeStock.pb }}</span></div>
                      <div class="m-cell"><span class="m-lbl">市盈率(动)</span><span class="m-val">{{ activeStock.peDynamic }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">委 比</span><span class="m-val" :class="String(activeStock.weibi).startsWith('-') ? 'down' : 'up'">{{ activeStock.weibi }}</span></div>
                      <div class="m-cell"><span class="m-lbl">量 比</span><span class="m-val">{{ activeStock.volumeRatio }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">股息TTM</span><span class="m-val">{{ activeStock.dividendTTM }}</span></div>
                      <div class="m-cell"><span class="m-lbl">股息率TTM</span><span class="m-val">{{ activeStock.dividendYieldTTM }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">52周最高</span><span class="m-val up">{{ fmtPx(activeStock.high52, 3) }}</span></div>
                      <div class="m-cell"><span class="m-lbl">52周最低</span><span class="m-val down">{{ fmtPx(activeStock.low52, 3) }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">历史最高</span><span class="m-val up">{{ fmtPx(activeStock.historyHigh, 3) }}</span></div>
                      <div class="m-cell"><span class="m-lbl">历史最低</span><span class="m-val down">{{ fmtPx(activeStock.historyLow, 3) }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">平均价</span><span class="m-val up">{{ fmtPx(activeStock.avgPrice, 3) }}</span></div>
                      <div class="m-cell"><span class="m-lbl">振 幅</span><span class="m-val">{{ activeStock.amplitude }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">换手率</span><span class="m-val">{{ activeStock.turnoverRate }}</span></div>
                      <div class="m-cell"><span class="m-lbl">每 手</span><span class="m-val">{{ activeStock.lotSize }}</span></div>
                    </div>
                    <div class="m-row">
                      <div class="m-cell"><span class="m-lbl">Beta ⓘ</span><span class="m-val">{{ activeStock.beta }}</span></div>
                      <div class="m-cell"><span class="m-lbl"></span><span class="m-val"></span></div>
                    </div>
                  </template>
                </div>

                <!-- 底部展开 / 收起触发横条 (点击在右栏原位平滑展开) -->
                <div class="info-expand-toggle-bar" @click="isInfoExpanded = !isInfoExpanded">
                  <div class="toggle-line"></div>
                  <div class="toggle-btn-circle" :class="{ expanded: isInfoExpanded }">
                    <el-icon v-if="!isInfoExpanded"><ArrowDown /></el-icon>
                    <el-icon v-else><ArrowUp /></el-icon>
                  </div>
                  <div class="toggle-line"></div>
                </div>
              </div>
            </el-tab-pane>

            <!-- 1.2 盘口 Tab -->
            <el-tab-pane label="盘口" name="depth">
              <div class="orderbook-wrap">
                <!-- 卖盘 (Asks 10 -> 1) -->
                <div class="order-section asks">
                  <div
                    v-for="ask in activeStock.asks"
                    :key="ask.level"
                    class="book-row ask-line"
                    @click="fillOrderPrice(ask.price)"
                  >
                    <div class="depth-bar-fill ask-fill" :style="{ width: `${ask.percent}%` }"></div>
                    <span class="level-tag">{{ ask.level }}</span>
                    <span class="price-cell down">{{ fmtPx(ask.price) }}</span>
                    <span class="vol-cell">{{ ask.volume.toLocaleString() }}</span>
                  </div>
                </div>

                <!-- 中间现价与价差条 -->
                <div class="book-mid-divider">
                  <span class="mid-price-tag" :class="heroPriceClass">{{ fmtPx(activeStock.price, 3) }}</span>
                  <span class="spread-hint">买卖价差 0.05</span>
                </div>

                <!-- 买盘 (Bids 1 -> 10) -->
                <div class="order-section bids">
                  <div
                    v-for="bid in activeStock.bids"
                    :key="bid.level"
                    class="book-row bid-line"
                    @click="fillOrderPrice(bid.price)"
                  >
                    <div class="depth-bar-fill bid-fill" :style="{ width: `${bid.percent}%` }"></div>
                    <span class="level-tag">{{ bid.level }}</span>
                    <span class="price-cell up">{{ fmtPx(bid.price) }}</span>
                    <span class="vol-cell">{{ bid.volume.toLocaleString() }}</span>
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <!-- 1.3 逐笔 Tab -->
            <el-tab-pane label="逐笔" name="trades">
              <div class="trades-list-stream">
                <div class="stream-header-row">
                  <span>时间</span>
                  <span>价格</span>
                  <span>量(股)</span>
                  <span>性质</span>
                </div>
                <div
                  v-for="(t, idx) in activeStock.trades"
                  :key="idx"
                  class="stream-item-row"
                >
                  <span class="col-time">{{ t.time }}</span>
                  <span class="col-price" :class="t.side === 'buy' ? 'up' : 'down'">{{ fmtPx(t.price) }}</span>
                  <span class="col-vol">{{ t.volume }}</span>
                  <span class="col-side" :class="t.side === 'buy' ? 'side-b' : 'side-s'">
                    {{ t.side === 'buy' ? '买盘' : '卖盘' }}
                  </span>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>

        <!-- 2. 标的量化区间微卡 (大幅压缩高度，紧凑精致) -->
        <div class="range-metric-card">
          <div class="range-top-info">
            <span class="r-lbl">52周价格区间</span>
            <span class="r-sub">当前处于 {{ get52WeekPosition() }}% 分位</span>
          </div>
          <div class="range-track-bar">
            <span class="r-low">{{ fmtPx(activeStock.low52) }}</span>
            <div class="track-bg">
              <div class="track-dot" :style="{ left: `${get52WeekPosition()}%` }"></div>
            </div>
            <span class="r-high">{{ fmtPx(activeStock.high52) }}</span>
          </div>
          <div class="range-extra-info">
            <span>Beta系数: <strong>{{ activeStock.beta }}</strong></span>
            <span>股息率: <strong>{{ activeStock.dividendYield }}</strong></span>
          </div>
        </div>

        <!-- 3. 专业级快捷交易下单面板 (全面压缩高度与间距，精致紧凑) -->
        <div class="quick-trade-card">
          <!-- 方向选择按钮 (买入 / 卖出) -->
          <div class="trade-side-switcher">
            <button
              class="side-btn buy-btn"
              :class="{ active: tradeForm.side === 'BUY' }"
              @click="tradeForm.side = 'BUY'"
            >
              买入 {{ activeStock.symbol }}
            </button>
            <button
              class="side-btn sell-btn"
              :class="{ active: tradeForm.side === 'SELL' }"
              @click="tradeForm.side = 'SELL'"
            >
              卖出 {{ activeStock.symbol }}
            </button>
          </div>

          <!-- 订单类型 -->
          <div class="form-item-line">
            <span class="f-lbl">类型</span>
            <el-radio-group v-model="tradeForm.type" size="small" class="order-type-radios">
              <el-radio-button value="LIMIT">限价单 LO</el-radio-button>
              <el-radio-button value="MARKET">市价单 MO</el-radio-button>
            </el-radio-group>
          </div>

          <!-- 委托价格 -->
          <div class="form-item-line" v-if="tradeForm.type === 'LIMIT'">
            <span class="f-lbl">价格</span>
            <div class="stepper-wrap">
              <el-input-number
                v-model="tradeForm.price"
                :precision="2"
                :step="0.05"
                size="small"
                controls-position="right"
                style="width: 100%"
              />
              <button class="fill-latest-btn" @click="fillOrderPrice(activeStock.price)">最新</button>
            </div>
          </div>

          <!-- 委托数量 -->
          <div class="form-item-line">
            <span class="f-lbl">数量</span>
            <el-input-number
              v-model="tradeForm.quantity"
              :min="1"
              :step="10"
              size="small"
              controls-position="right"
              style="width: 100%"
            />
          </div>

          <!-- 快捷仓位比例胶囊 -->
          <div class="ratio-pill-row">
            <button class="r-pill" @click="applyRatio(0.25)">25%</button>
            <button class="r-pill" @click="applyRatio(0.50)">50%</button>
            <button class="r-pill" @click="applyRatio(0.75)">75%</button>
            <button class="r-pill" @click="applyRatio(1.00)">全仓</button>
          </div>

          <!-- 名义金额与预估信息 -->
          <div class="trade-cost-summary">
            <div class="cost-line">
              <span>名义金额:</span>
              <strong class="cost-val">\$ {{ calcNotional().toLocaleString('en-US', { minimumFractionDigits: 2 }) }}</strong>
            </div>
            <div class="cost-sub-line">
              <span>购买力: \$ {{ accountCash.toLocaleString('en-US', { minimumFractionDigits: 2 }) }}</span>
              <span>预估费用: \$ 1.00</span>
            </div>
          </div>

          <!-- 极速下单按钮 -->
          <el-button
            class="do-order-btn"
            :class="tradeForm.side === 'BUY' ? 'btn-order-buy' : 'btn-order-sell'"
            :loading="orderSubmitting"
            @click="submitSimulatedOrder"
          >
            极速{{ tradeForm.side === 'BUY' ? '买入' : '卖出' }} {{ activeStock.symbol }} ({{ tradeForm.quantity }} 股)
          </el-button>
        </div>

        <!-- 4. 当日委托与持仓小型监控面板 -->
        <div class="bottom-orders-card">
          <el-tabs v-model="bottomRightTab" class="tight-tabs">
            <el-tab-pane :label="`当日委托 (${mockOrders.length})`" name="orders">
              <div class="orders-scroll-list">
                <div v-for="o in mockOrders" :key="o.id" class="order-item-card">
                  <div class="o-main">
                    <span class="o-side-badge" :class="o.side === 'BUY' ? 'up' : 'down'">
                      {{ o.side === 'BUY' ? '买' : '卖' }}
                    </span>
                    <span class="o-code">{{ o.symbol }}</span>
                    <span class="o-detail">{{ o.quantity }}股 @ {{ o.price }}</span>
                  </div>
                  <div class="o-act">
                    <el-tag size="small" :type="o.status === '已成交' ? 'success' : 'info'">{{ o.status }}</el-tag>
                    <el-button v-if="o.open || o.status === '待成交' || o.status === '已提交'" link type="danger" size="small" @click="cancelSimulatedOrder(o.id)">撤单</el-button>
                  </div>
                </div>
                <div v-if="!mockOrders.length" class="empty-hint-text">暂无当日委托</div>
              </div>
            </el-tab-pane>

            <el-tab-pane :label="`持仓 (${mockPositions.length})`" name="pos">
              <div class="positions-scroll-list">
                <div
                  v-for="p in mockPositions"
                  :key="p.symbol"
                  class="pos-item-card"
                  @click="selectStockBySymbol(p.symbol)"
                >
                  <div class="p-main">
                    <span class="p-code">{{ p.symbol }}</span>
                    <span class="p-qty">{{ p.quantity }} 股</span>
                  </div>
                  <div class="p-stat">
                    <div class="p-val">市值 {{ fmtNum(p.quantity * p.currentPrice) }}</div>
                    <div class="p-pnl" :class="p.pnl >= 0 ? 'up' : 'down'">
                      {{ p.pnl >= 0 ? '+' : '' }}{{ p.pnlRate }}%
                    </div>
                  </div>
                </div>
                <div v-if="!mockPositions.length" class="empty-hint-text">暂无持仓数据</div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup name="MarketTerminal">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage, ElNotification, ElMessageBox } from 'element-plus'
import {
  Search, Refresh, FullScreen, StarFilled, ArrowDown, ArrowUp,
  MagicStick, Document, PieChart, Bell
} from '@element-plus/icons-vue'
import echarts from '@/utils/echarts'
import { isDarkTheme } from '@/utils/echartsTheme'
import { formatBeijingTime } from '@/utils/beijingTime'
import useSettingsStore from '@/store/modules/settings'
import {
  mockMarketIndices,
  mockStockUniverse,
  getStockIntraday,
  getStockKline
} from './mockData'
import { shouldShowMarketChip, getMarketSessionStatus } from './sessionHours'
import { getMarketIndexQuotes, getMarketWatchlistOverview, listMarketWatchlist, getKline, getSymbolOverview, getSymbolContent, listInstrumentUniverse } from '@/api/market'
import {
  getTradeAccount,
  getTradePositions,
  getTradeOrders,
  submitTradeOrder,
  cancelTradeOrder,
  getTradeQuoteDepth,
  getTradeQuoteTrades,
  getTradeQuoteKline,
  getTradeQuoteSnapshot,
  getAutoTradeStatus,
  saveAutoTradeSettings
} from '@/api/trade'

const settingsStore = useSettingsStore()

// ====================== 状态定义 ======================
const isFullscreen = ref(false)
const isFavorited = ref(true)
const isInfoExpanded = ref(false) // 默认精简3行指标，点击在右栏原位展开全部26项
const searchKeyword = ref('')
const currentGroup = ref('全部')
const watchFilterKw = ref('')
const sortField = ref('changeRate')
const sortOrder = ref('desc')
const activeSymbol = ref('AAPL')
const currentPeriod = ref('daily')
const mainIndicators = ref(['MA'])
const subIndicator = ref('VOL')
const activeBottomTab = ref('ai')
const rightTopTab = ref('info') // 默认打开右侧「基本信息」Tab
const bottomRightTab = ref('orders')
const orderSubmitting = ref(false)
const accountCash = ref(0)
const cashCurrency = ref('USD')
const liveMode = ref(false)
const configured = ref(false)
const autoTradeEnabled = ref(false)
const autoTradeConfigured = ref(false)
const autoTradeSaving = ref(false)
const sessionClock = ref(0)

// 标的数据与大盘指数
const marketIndices = ref([...mockMarketIndices])
const stockUniverse = ref([blankStock({ symbol: 'AAPL', name: 'Apple', market: 'US' })])

// 价格跳动闪烁状态
const priceFlashMap = ref({})
const heroFlashState = ref('')

// 周期配置
const periodOptions = [
  { label: '分时', value: 'intraday' },
  { label: '5日', value: '5d' },
  { label: '日K', value: 'daily' },
  { label: '周K', value: 'weekly' },
  { label: '月K', value: 'monthly' },
  { label: '5分', value: 'm5' }
]

// 快捷交易表单
const tradeForm = ref({
  side: 'BUY',
  type: 'LIMIT',
  price: 0,
  quantity: 100
})

const mockOrders = ref([])
const mockPositions = ref([])

// ECharts 实例引用
const chartContainerRef = ref(null)
let chartInstance = null
let liveTickTimer = null
let sessionTimer = null
let bookTimer = null
let snapshotTimer = null
let newsTimer = null
let searchTimer = null
let searchSeq = 0
let watchlistInitDone = false

// ====================== 计算属性 ======================
const activeStock = computed(() => {
  return stockUniverse.value.find(s => s.symbol === activeSymbol.value) || stockUniverse.value[0] || blankStock({ symbol: 'AAPL', market: 'US' })
})

const activeSession = computed(() => getMarketSessionStatus(activeStock.value?.market || 'US'))

function stockGroupsOf(s) {
  if (Array.isArray(s?.groups) && s.groups.length) return s.groups
  if (s?.group) return [s.group]
  return []
}

const watchGroupNames = computed(() => {
  const names = ['全部']
  const seen = new Set(names)
  stockUniverse.value.forEach((s) => {
    stockGroupsOf(s).forEach((g) => {
      if (g && !seen.has(g)) {
        seen.add(g)
        names.push(g)
      }
    })
  })
  return names
})

const watchStats = computed(() => {
  const list = stockUniverse.value || []
  let up = 0
  let down = 0
  let flat = 0
  let sum = 0
  let n = 0
  list.forEach((s) => {
    const r = Number(s.changeRate)
    if (!Number.isFinite(r)) {
      flat += 1
      return
    }
    sum += r
    n += 1
    if (r > 0.0001) up += 1
    else if (r < -0.0001) down += 1
    else flat += 1
  })
  const total = Math.max(1, list.length)
  return {
    up,
    down,
    flat,
    avg: n ? sum / n : 0,
    upPct: Math.round((up / total) * 100),
    downPct: Math.round((down / total) * 100)
  }
})

const hasCapitalFlow = computed(() => {
  const f = activeStock.value?.capitalFlow
  if (!f || f._live !== true) return false
  return true
})

// 动态开盘指数列表：美股全时段始终展示，港股和A股只在开盘时显示
const activeMarketIndices = computed(() => {
  sessionClock.value
  return marketIndices.value
    .map(idx => ({
      ...idx,
      sessionStatus: getMarketSessionStatus(idx.market)
    }))
    .filter(idx => shouldShowMarketChip(idx.market))
})

const heroPriceClass = computed(() => {
  const isUp = activeStock.value.changeRate >= 0
  return `${isUp ? 'up' : 'down'} ${heroFlashState.value}`
})

const filteredStocks = computed(() => {
  let list = stockUniverse.value
  if (currentGroup.value !== '全部') {
    const grp = currentGroup.value
    list = list.filter((s) => {
      const gs = Array.isArray(s.groups) && s.groups.length ? s.groups : []
      if (gs.includes(grp)) return true
      return s.group === grp
    })
  }
  if (watchFilterKw.value.trim()) {
    const kw = watchFilterKw.value.trim().toUpperCase()
    list = list.filter(s => s.symbol.includes(kw) || s.name.includes(kw))
  }
  return list
})

const sortedWatchStocks = computed(() => {
  const list = [...filteredStocks.value]
  const field = sortField.value
  const order = sortOrder.value
  list.sort((a, b) => {
    let vA = a[field]
    let vB = b[field]
    if (typeof vA === 'string') vA = parseFloat(vA) || 0
    if (typeof vB === 'string') vB = parseFloat(vB) || 0
    return order === 'desc' ? vB - vA : vA - vB
  })
  return list
})

// ====================== 自选与标的交互 ======================
function handleGroupChange(grp) {
  currentGroup.value = grp
  const first = filteredStocks.value[0]
  if (first) selectStock(first)
}

function toggleFavorite() {
  isFavorited.value = !isFavorited.value
  ElMessage.success(isFavorited.value ? '已添加到自选关注' : '已取消自选')
}

function toggleSort(field) {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
}

function selectStock(item) {
  activeSymbol.value = item.symbol
  tradeForm.value.price = item.price || tradeForm.value.price
  loadLiveKline().then(() => renderECharts())
  loadBrokerSnapshot()
  if (rightTopTab.value === 'depth' || rightTopTab.value === 'trades') {
    loadLiveDepth()
  } else {
    window.setTimeout(() => loadLiveDepth(), 400)
  }
  window.setTimeout(() => loadSymbolNews(), 600)
}

function selectStockBySymbol(sym) {
  const parsed = splitBrokerSymbol(sym)
  const target = stockUniverse.value.find(s => s.symbol === parsed.symbol || s.symbol === sym)
  if (target) selectStock(target)
}

function stockIdentity(s) {
  return `${String(s?.symbol || '').toUpperCase()}.${String(s?.market || 'US').toUpperCase()}`
}

function matchStockQuery(s, q) {
  if (!q) return true
  const kw = q.toLowerCase()
  return String(s.symbol || '').toLowerCase().includes(kw)
    || String(s.name || '').toLowerCase().includes(kw)
}

function querySearchStocks(queryString, cb) {
  const q = (queryString || '').trim()
  const watchHits = stockUniverse.value.filter((s) => matchStockQuery(s, q))
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  const seq = ++searchSeq
  if (!q) {
    cb(watchHits.slice(0, 15))
    return
  }
  searchTimer = setTimeout(async () => {
    searchTimer = null
    try {
      const res = await listInstrumentUniverse({ keyword: q, pageNum: 1, pageSize: 15 })
      if (seq !== searchSeq) return
      const rows = res.rows || res.data?.rows || []
      const seen = new Set()
      const out = []
      watchHits.forEach((s) => {
        const k = stockIdentity(s)
        if (seen.has(k)) return
        seen.add(k)
        out.push(s)
      })
      rows.forEach((r) => {
        const row = {
          symbol: r.symbol,
          name: r.name || r.symbol,
          market: String(r.market || 'US').toUpperCase(),
          category: r.category || '',
          price: r.price,
          changeRate: r.changeRate,
          tradeDate: r.tradeDate
        }
        const k = stockIdentity(row)
        if (seen.has(k)) return
        seen.add(k)
        out.push(row)
      })
      cb(out)
    } catch {
      if (seq !== searchSeq) return
      cb(watchHits)
    }
  }, 200)
}

function handleSearchSelect(item) {
  if (!item?.symbol) return
  const mkt = String(item.market || 'US').toUpperCase()
  let target = stockUniverse.value.find(
    (s) => s.symbol === item.symbol && String(s.market || 'US').toUpperCase() === mkt
  )
  if (!target) {
    target = mapWatchRow(item)
    stockUniverse.value = [...stockUniverse.value, target]
  }
  selectStock(target)
  searchKeyword.value = ''
}

function fillOrderPrice(p) {
  const n = Number(p)
  if (!Number.isFinite(n) || n <= 0) return
  tradeForm.value.price = Number(n.toFixed(2))
  ElMessage.info(`已填入委托价: ${n.toFixed(2)}`)
}

function applyRatio(ratio) {
  const price = tradeForm.value.price || activeStock.value.price
  if (tradeForm.value.side === 'BUY') {
    const maxAfford = Math.floor((accountCash.value * ratio) / price)
    tradeForm.value.quantity = Math.max(1, maxAfford)
  } else {
    const pos = mockPositions.value.find(p => splitBrokerSymbol(p.symbol).symbol === activeStock.value.symbol)
    const hold = pos ? pos.quantity : 100
    tradeForm.value.quantity = Math.max(1, Math.floor(hold * ratio))
  }
}

function calcNotional() {
  const p = tradeForm.value.type === 'LIMIT' ? tradeForm.value.price : activeStock.value.price
  return (p || 0) * (tradeForm.value.quantity || 0)
}

function get52WeekPosition() {
  const stock = activeStock.value
  const range = stock.high52 - stock.low52
  if (range <= 0) return 50
  const pos = ((stock.price - stock.low52) / range) * 100
  return Math.min(100, Math.max(0, Math.round(pos)))
}

function renderSparklinePath(arr) {
  if (!arr || arr.length < 2) return ''
  const min = Math.min(...arr)
  const max = Math.max(...arr)
  const range = max - min || 1
  const width = 60
  const height = 20
  const step = width / (arr.length - 1)
  
  return arr.reduce((acc, val, idx) => {
    const x = idx * step
    const y = height - ((val - min) / range) * (height - 4) - 2
    return `${acc} ${idx === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
  }, '')
}

function getPriceFlashClass(sym) {
  return priceFlashMap.value[sym] || ''
}

function formatVolume(vol) {
  if (vol >= 100000000) return `${(vol / 100000000).toFixed(2)} 亿`
  if (vol >= 10000) return `${(vol / 10000).toFixed(2)} 万`
  return String(vol)
}

function formatTurnover(turnover) {
  if (turnover >= 100000000) return `${(turnover / 100000000).toFixed(2)} 亿`
  if (turnover >= 10000) return `${(turnover / 10000).toFixed(2)} 万`
  return String(turnover)
}

function setPeriod(p) {
  currentPeriod.value = p
  loadLiveKline().then(() => renderECharts())
}

// ====================== 快捷交易操作 ======================
async function submitSimulatedOrder() {
  const notional = calcNotional()
  if (tradeForm.value.side === 'BUY' && accountCash.value > 0 && notional > accountCash.value) {
    ElMessage.error('可用资金不足以支付当前委托名义金额！')
    return
  }
  orderSubmitting.value = true
  try {
    const res = await submitTradeOrder({
      symbol: activeStock.value.symbol,
      market: activeStock.value.market || 'US',
      side: tradeForm.value.side === 'SELL' ? 'sell' : 'buy',
      orderType: tradeForm.value.type === 'MARKET' ? 'MO' : 'LO',
      quantity: tradeForm.value.quantity,
      price: tradeForm.value.type === 'LIMIT' ? tradeForm.value.price : undefined
    })
    const payload = res.data || {}
    ElNotification({
      title: payload.ok === false ? '下单未成功' : (res.msg || '委托已提交'),
      message: payload.message || `${tradeForm.value.side === 'BUY' ? '买入' : '卖出'} ${activeStock.value.symbol} ${tradeForm.value.quantity} 股`,
      type: payload.ok === false ? 'warning' : 'success',
      duration: 3500
    })
    await loadLiveBook()
  } catch (e) {
    ElMessage.error(e.message || e.msg || '下单失败')
  } finally {
    orderSubmitting.value = false
  }
}

async function cancelSimulatedOrder(orderId) {
  try {
    await cancelTradeOrder(orderId)
    ElMessage.info(`已提交撤单 ${orderId}`)
    await loadLiveBook()
  } catch (e) {
    ElMessage.error(e.message || e.msg || '撤单失败')
  }
}

function pickNum(...vals) {
  for (const v of vals) {
    if (v == null || v === '') continue
    const n = Number(v)
    if (Number.isFinite(n)) return n
  }
  return 0
}

function fmtNum(v, d = 2) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(d) : '--'
}

function fmtPx(v, d = 2) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return '--'
  return n.toFixed(d)
}

function fmtSigned(v, d = 2) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${n >= 0 ? '+' : ''}${n.toFixed(d)}`
}

function dash(v) {
  if (v === 0) return '0'
  if (v == null || v === '' || v === '--') return '--'
  return v
}

/** 展示北京时间；带 Z/偏移才换算，朴素字符串当墙上时钟。 */
function toBeijingDisplay(raw, pattern = '{y}-{m}-{d} {h}:{i}:{s}') {
  if (raw == null || raw === '') return ''
  const s = String(raw).trim()
  if (!s) return ''
  if (/^\d{4}[-/]\d{1,2}[-/]\d{1,2}$/.test(s)) return s.replace(/\//g, '-')
  return formatBeijingTime(s, pattern) || s.replace('T', ' ').replace(/[zZ]$/, '')
}

function axisTimeLabel(raw, fallback) {
  const shown = toBeijingDisplay(raw, '{h}:{i}')
  if (shown) {
    const m = String(shown).match(/(\d{1,2}:\d{2})/)
    if (m) return m[1].padStart(5, '0')
    return shown
  }
  return fallback != null ? String(fallback) : ''
}

function axisDateLabel(raw) {
  return toBeijingDisplay(raw) || String(raw || '')
}

function currencyOf(market) {
  const m = String(market || 'US').toUpperCase()
  if (m === 'HK') return 'HKD'
  if (m === 'CN' || m === 'SH' || m === 'SZ') return 'CNY'
  return 'USD'
}

function splitBrokerSymbol(raw) {
  const text = String(raw || '').trim()
  const m = text.match(/^(.*)\.(US|HK|SH|SZ|CN)$/i)
  if (!m) return { symbol: text, market: 'US' }
  const suffix = m[2].toUpperCase()
  const market = suffix === 'SH' || suffix === 'SZ' ? 'CN' : suffix
  return { symbol: m[1], market }
}

function blankStock(r = {}) {
  const market = String(r.market || 'US').toUpperCase()
  return {
    symbol: r.symbol || '',
    name: r.name || r.symbol || '',
    market,
    currency: r.currency || currencyOf(market),
    category: r.category || '',
    groups: Array.isArray(r.groups)
      ? r.groups.map((g) => String(g).trim()).filter(Boolean)
      : (r.group && r.group !== '全部' ? [r.group] : []),
    group: (r.groups && r.groups[0]) || r.note || r.group || '全部',
    price: 0,
    prevClose: 0,
    open: 0,
    high: 0,
    low: 0,
    change: 0,
    changeRate: 0,
    volume: 0,
    turnover: 0,
    turnoverRate: '--',
    amplitude: '--',
    volumeRatio: '--',
    pe: '--',
    peTTM: '--',
    peStatic: '--',
    peDynamic: '--',
    pb: '--',
    marketCap: '--',
    floatMarketCap: '--',
    totalShares: '--',
    floatShares: '--',
    weibi: '--',
    dividendTTM: '--',
    dividendYield: '--',
    dividendYieldTTM: '--',
    lotSize: '--',
    avgPrice: 0,
    beta: '--',
    historyHigh: 0,
    historyLow: 0,
    high52: 0,
    low52: 0,
    aiScore: null,
    aiVerdict: '',
    aiSummary: '',
    factors: [],
    news: [],
    capitalFlow: { superIn: 0, superOut: 0, largeIn: 0, largeOut: 0, midIn: 0, midOut: 0, smallIn: 0, smallOut: 0, netInflow: 0, _live: false },
    sparkline: [],
    trades: [],
    bids: [],
    asks: [],
    liveBars: [],
    liveBarsKind: '',
    quoteTime: toBeijingDisplay(r.tradeDate) || r.tradeDate || '',
    analysis: r.analysis || null
  }
}

function applyQuoteMath(s, src = {}) {
  const last = pickNum(src.last, src.price, src.close, s.price)
  let changeRate = pickNum(src.changeRate, src.changePct)
  let prevClose = pickNum(src.prevClose)
  let change = pickNum(src.change)
  if (!prevClose && last && changeRate) prevClose = last / (1 + changeRate / 100)
  if (!change && last && prevClose) change = last - prevClose
  if (!changeRate && last && prevClose) changeRate = ((last / prevClose) - 1) * 100
  s.price = last
  s.prevClose = prevClose || last
  s.change = change
  s.changeRate = changeRate
  s.open = pickNum(src.open, s.open, last)
  s.high = pickNum(src.high, s.high, last)
  s.low = pickNum(src.low, s.low, last)
  s.volume = pickNum(src.volume, s.volume)
  s.turnover = pickNum(src.turnover, s.turnover)
  if (src.tradeDate || src.date) s.quoteTime = toBeijingDisplay(src.tradeDate || src.date)
  return s
}

function mapWatchRow(r) {
  const s = blankStock(r)
  applyQuoteMath(s, r)
  const a = r.analysis || {}
  if (a.confidence != null) s.aiScore = pickNum(a.confidence)
  s.aiVerdict = a.recommendation || a.stance || ''
  s.aiSummary = a.summary || a.operationAdvice || r.summary || ''
  return s
}

function fillIfEmpty(obj, key, val) {
  if (val == null || val === '' || val === '--') return
  const cur = obj[key]
  const empty = cur == null || cur === '' || cur === '--' || cur === 0
  if (empty) obj[key] = val
}

function fmtCap(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return null
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}万亿`
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return String(Math.round(n))
}

function fmtRate(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return null
  // 长桥换手/振幅/股息率多为百分数；仅极小值按小数换算
  const p = Math.abs(n) < 0.05 ? n * 100 : n
  return `${p.toFixed(2)}%`
}

function toWan(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return 0
  return Math.round(n / 10000)
}

function fmtPe(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return null
  return n.toFixed(2)
}

function applyBrokerSnapshot(s, snap) {
  if (!s || !snap || snap.available === false) return
  fillIfEmpty(s, 'name', snap.name)
  fillIfEmpty(s, 'currency', snap.currency)
  // 现价/今开/高低/量额：长桥实时优先于日K昨收，避免盘后仍停在历史收盘
  if (snap.last) {
    applyQuoteMath(s, snap)
  } else {
    fillIfEmpty(s, 'open', snap.open)
    fillIfEmpty(s, 'high', snap.high)
    fillIfEmpty(s, 'low', snap.low)
    fillIfEmpty(s, 'volume', snap.volume)
    fillIfEmpty(s, 'turnover', snap.turnover)
    fillIfEmpty(s, 'prevClose', snap.prevClose)
    fillIfEmpty(s, 'change', snap.change)
    fillIfEmpty(s, 'changeRate', snap.changeRate)
    fillIfEmpty(s, 'price', snap.last)
  }
  const peTtm = fmtPe(snap.peTtm)
  const peStatic = fmtPe(snap.peStatic)
  fillIfEmpty(s, 'pe', peTtm)
  fillIfEmpty(s, 'peTTM', peTtm)
  fillIfEmpty(s, 'peStatic', peStatic || peTtm)
  fillIfEmpty(s, 'pb', snap.pb != null && Number.isFinite(Number(snap.pb)) ? Number(snap.pb).toFixed(3) : null)
  fillIfEmpty(s, 'marketCap', fmtCap(snap.marketCap))
  fillIfEmpty(s, 'floatMarketCap', fmtCap(snap.floatMarketCap || (snap.static?.circulatingShares && snap.last ? snap.last * snap.static.circulatingShares : null)))
  fillIfEmpty(s, 'turnoverRate', fmtRate(snap.turnoverRate))
  fillIfEmpty(s, 'volumeRatio', snap.volumeRatio != null ? Number(snap.volumeRatio).toFixed(2) : null)
  fillIfEmpty(s, 'amplitude', fmtRate(snap.amplitude))
  fillIfEmpty(s, 'avgPrice', snap.avgPrice)
  fillIfEmpty(s, 'dividendYield', fmtRate(snap.dividendYield))
  fillIfEmpty(s, 'dividendYieldTTM', fmtRate(snap.dividendYield))
  fillIfEmpty(s, 'dividendTTM', snap.dividendTtm != null && Number.isFinite(Number(snap.dividendTtm)) ? Number(snap.dividendTtm).toFixed(3) : null)
  fillIfEmpty(s, 'lotSize', snap.lotSize != null ? `${snap.lotSize}股` : null)
  fillIfEmpty(s, 'totalShares', fmtCap(snap.static?.totalShares))
  fillIfEmpty(s, 'floatShares', fmtCap(snap.static?.circulatingShares))
  fillIfEmpty(s, 'high52', snap.high52)
  fillIfEmpty(s, 'low52', snap.low52)
  fillIfEmpty(s, 'historyHigh', snap.historyHigh)
  fillIfEmpty(s, 'historyLow', snap.historyLow)
  fillIfEmpty(s, 'peDynamic', fmtPe(snap.peDynamic))
  fillIfEmpty(s, 'beta', snap.beta != null && Number.isFinite(Number(snap.beta)) ? Number(snap.beta).toFixed(3) : null)
  fillIfEmpty(s, 'category', snap.category)
  if (snap.timestamp) fillIfEmpty(s, 'quoteTime', toBeijingDisplay(snap.timestamp))
  const cap = snap.capital || {}
  if (cap.in || cap.out || cap.net != null) {
    const inn = cap.in || {}
    const out = cap.out || {}
    s.capitalFlow = {
      superIn: 0,
      superOut: 0,
      largeIn: toWan(inn.large),
      largeOut: toWan(out.large),
      midIn: toWan(inn.medium),
      midOut: toWan(out.medium),
      smallIn: toWan(inn.small),
      smallOut: toWan(out.small),
      netInflow: toWan(cap.net),
      _live: true
    }
  }
  if (Array.isArray(snap.news) && snap.news.length && !(s.news && s.news.length)) {
    s.news = snap.news.map((n) => ({
      id: n.id || n.title,
      title: n.title,
      source: n.source || '长桥',
      time: toBeijingDisplay(n.time, '{m}-{d} {h}:{i}') || toBeijingDisplay(n.time),
      sentiment: guessNewsSentiment(n.title)
    }))
  }
}

function applyBarsToQuote(s, bars) {
  const klines = liveKlinesFromBars(bars)
  if (!klines || !klines.length) return
  const last = klines[klines.length - 1]
  const prev = klines.length > 1 ? klines[klines.length - 2] : null
  const isMinute = s.liveBarsKind === 'minute'
  if (isMinute) {
    const highs = klines.map((k) => k.high).filter((n) => n > 0)
    const lows = klines.map((k) => k.low).filter((n) => n > 0)
    applyQuoteMath(s, {
      last: last.close,
      open: klines[0].open,
      high: highs.length ? Math.max(...highs) : last.high,
      low: lows.length ? Math.min(...lows) : last.low,
      volume: klines.reduce((sum, k) => sum + (Number(k.volume) || 0), 0),
      prevClose: s.prevClose,
      tradeDate: last.date
    })
  } else {
    fillIfEmpty(s, 'open', last.open)
    fillIfEmpty(s, 'high', last.high)
    fillIfEmpty(s, 'low', last.low)
    fillIfEmpty(s, 'volume', last.volume)
    if (!s.price) {
      applyQuoteMath(s, {
        last: last.close,
        open: last.open,
        high: last.high,
        low: last.low,
        volume: last.volume,
        prevClose: prev ? prev.close : s.prevClose,
        tradeDate: last.date
      })
    }
  }
  s.sparkline = klines.slice(-24).map((k) => k.close)
}

function barNum(b, keys) {
  for (const k of keys) {
    const n = Number(b?.[k])
    if (Number.isFinite(n)) return n
  }
  return 0
}

function liveKlinesFromBars(bars) {
  if (!Array.isArray(bars) || !bars.length) return null
  const out = []
  for (const b of bars) {
    const open = barNum(b, ['open', 'o'])
    const close = barNum(b, ['close', 'c', 'price', 'last'])
    const high = barNum(b, ['high', 'h'])
    const low = barNum(b, ['low', 'l'])
    const volume = barNum(b, ['volume', 'vol', 'v'])
    if (!open && !close) continue
    out.push({
      date: String(b.date || b.time || b.tradeDate || ''),
      open,
      close,
      high: high || Math.max(open, close),
      low: low || Math.min(open, close),
      volume
    })
  }
  return out.length ? out : null
}

function liveIntradayFromBars(bars, kind) {
  const klines = liveKlinesFromBars(bars)
  if (!klines || !klines.length) return null
  const clocked = klines.filter((k) => /\d{1,2}:\d{2}/.test(String(k.date)))
  // 分钟 OHLC 用收盘价画分时，不要求 8 根带时分的 bar；日 K 回退仍走蜡烛图
  const rows = kind === 'minute' ? klines : clocked
  if (!rows.length) return null
  let sum = 0
  return rows.map((k, i) => {
    const price = k.close || k.open
    sum += price
    return {
      time: axisTimeLabel(k.date, i),
      price: Number(price.toFixed(3)),
      avgPrice: Number((sum / (i + 1)).toFixed(3)),
      volume: k.volume
    }
  })
}

function klineRangeFor(period) {
  if (period === 'intraday' || period === '1min') return '-1d'
  if (period === 'm5' || period === '5min') return '-5d'
  if (period === '5d') return '-10d'
  if (period === 'weekly') return '-2y'
  if (period === 'monthly') return '-5y'
  return '-80d'
}

function isMinutePeriod(period) {
  return ['intraday', '1min', '5min', 'm5', '15min'].includes(period)
}

function normalizeBook(rows, side) {
  const list = (Array.isArray(rows) ? rows : [])
    .map((r, i) => ({
      price: pickNum(r.price),
      volume: pickNum(r.volume, r.size, r.qty),
      position: pickNum(r.position) || i + 1
    }))
    .filter((x) => x.price > 0)
  list.sort((a, b) => b.price - a.price)
  const maxVol = Math.max(1, ...list.map((x) => x.volume))
  if (side === 'ask') {
    return list.map((x, i) => ({
      level: `卖${list.length - i}`,
      price: x.price,
      volume: x.volume,
      percent: (x.volume / maxVol) * 100
    }))
  }
  return list.map((x, i) => ({
    level: `买${i + 1}`,
    price: x.price,
    volume: x.volume,
    percent: (x.volume / maxVol) * 100
  }))
}

function normalizeTrades(rows) {
  return (Array.isArray(rows) ? rows : []).map((t) => ({
    time: toBeijingDisplay(t.time || t.tradeTime, '{h}:{i}:{s}') || toBeijingDisplay(t.time || t.tradeTime),
    price: pickNum(t.price),
    volume: pickNum(t.volume, t.size, t.qty),
    side: String(t.side || '').toLowerCase().includes('sell') ? 'sell' : 'buy'
  }))
}

async function loadLiveIndices() {
  try {
    const res = await getMarketIndexQuotes()
    const items = res.data?.items || res.rows || []
    if (!items.length) return
    const mapped = items.map((q) => ({
      symbol: q.symbol,
      name: q.name || q.symbol,
      price: pickNum(q.last, q.price, q.close),
      change: pickNum(q.change),
      changeRate: pickNum(q.changePct, q.changeRate),
      market: String(q.market || 'US').toUpperCase()
    }))
    const liveUs = mapped.filter((x) => x.market === 'US')
    const liveAsia = mapped.filter((x) => x.market !== 'US')
    const fallbackUs = marketIndices.value.filter((x) => String(x.market || 'US').toUpperCase() === 'US')
    marketIndices.value = [
      ...(liveUs.length ? liveUs : fallbackUs),
      ...liveAsia
    ]
  } catch { /* 保留 mock 指数 */ }
}

function applyWatchlistItems(items) {
  if (!items.length) return
  const prev = activeStock.value
  liveMode.value = true
  stockUniverse.value = items.map(mapWatchRow)
  const list = filteredStocks.value
  const inFiltered = list.some((s) => s.symbol === activeSymbol.value)
  if (!watchlistInitDone) {
    watchlistInitDone = true
    const first = list[0]
    if (first && first.symbol !== activeSymbol.value) {
      selectStock(first)
    } else if (first) {
      activeSymbol.value = first.symbol
      tradeForm.value.price = first.price || tradeForm.value.price
    }
  } else if (!inFiltered && list[0]) {
    selectStock(list[0])
  }
  const cur = currentStock(prev?.symbol, prev?.market)
  if (cur && prev && cur.symbol === prev.symbol && Array.isArray(prev.liveBars) && prev.liveBars.length) {
    cur.liveBars = prev.liveBars
    cur.liveBarsKind = prev.liveBarsKind
    applyBarsToQuote(cur, prev.liveBars)
  }
}

async function loadLiveWatchlist() {
  try {
    const lite = await listMarketWatchlist({ pageNum: 1, pageSize: 200, enabled: '1' })
    const rows = lite.rows || lite.data?.rows || []
    if (Array.isArray(rows) && rows.length) applyWatchlistItems(rows)
  } catch { /* 无轻量清单时走总览 */ }
  try {
    const res = await getMarketWatchlistOverview({ timeout: 20000 })
    const items = res.data?.items || []
    if (items.length) applyWatchlistItems(items)
  } catch { /* 保留已有自选 */ }
}

function applyAccountPayload(accData) {
  configured.value = accData.configured === true
  const bals = Array.isArray(accData.balances) ? accData.balances : []
  const usd = bals.find((b) => String(b.currency || '').toUpperCase() === 'USD')
  const pick = usd || bals[0] || accData
  accountCash.value = pickNum(
    pick.availableCash,
    pick.buyPower,
    pick.maxFinanceAmount,
    pick.netAssets,
    pick.totalCash,
    accData.availableCash,
    accData.cash
  )
  cashCurrency.value = pick.currency || accData.currency || 'USD'
}

async function loadLiveAccount() {
  try {
    const acc = await getTradeAccount()
    applyAccountPayload(acc.data || {})
  } catch { /* 未配长桥时保留空资金 */ }
}

async function loadAutoTradeStatus() {
  try {
    const res = await getAutoTradeStatus()
    const data = res.data || {}
    autoTradeConfigured.value = data.configured === true
    autoTradeEnabled.value = !!data.autoTradeEnabled
  } catch {
    autoTradeConfigured.value = false
    autoTradeEnabled.value = false
  }
}

async function onToggleAutoTrade(val) {
  if (val && !autoTradeConfigured.value) {
    ElMessage.warning('未配置长桥 Key，无法打开自动交易')
    return
  }
  if (val) {
    try {
      await ElMessageBox.confirm(
        '打开后，本登录账户的定时扫描和止损将向长桥真实下单。确认打开？',
        '开启本账户自动交易',
        { type: 'warning', confirmButtonText: '确认打开', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }
  autoTradeSaving.value = true
  try {
    const res = await saveAutoTradeSettings({ autoTradeEnabled: Boolean(val) })
    const data = res.data || {}
    if (data.configured != null) autoTradeConfigured.value = data.configured === true
    autoTradeEnabled.value = !!data.autoTradeEnabled
    ElMessage.success(res.msg || (val ? '已开启自动交易' : '已关闭自动交易'))
  } catch (e) {
    ElMessage.warning(e.message || e.msg || '未配置长桥 Key，无法打开自动交易')
  } finally {
    autoTradeSaving.value = false
    loadAutoTradeStatus()
  }
}

async function loadLiveBook() {
  try {
    const acc = await getTradeAccount()
    applyAccountPayload(acc.data || {})
    const [pos, ord] = await Promise.all([
      getTradePositions(),
      getTradeOrders('today')
    ])
    const positions = pos.data?.positions || pos.data || []
    if (Array.isArray(positions) && positions.length) {
      mockPositions.value = positions.map((p) => {
        const parsed = splitBrokerSymbol(p.symbol)
        const q = stockUniverse.value.find((s) => s.symbol === parsed.symbol)
        const last = pickNum(q?.price, p.last, p.currentPrice, p.costPrice)
        const cost = pickNum(p.costPrice)
        const qty = pickNum(p.quantity, p.qty)
        const pnl = cost && last ? (last - cost) * qty : pickNum(p.unrealizedPnl, p.pnl)
        const pnlRate = cost ? ((last / cost) - 1) * 100 : pickNum(p.unrealizedPnlPct)
        return {
          symbol: p.symbol,
          code: parsed.symbol,
          market: parsed.market,
          quantity: qty,
          costPrice: cost,
          currentPrice: last,
          pnl,
          pnlRate: Number.isFinite(pnlRate) ? pnlRate.toFixed(2) : ''
        }
      })
    }
    const orders = ord.data?.orders || ord.data || []
    if (Array.isArray(orders)) {
      mockOrders.value = orders.map((o) => ({
        id: o.orderId || o.id,
        symbol: o.symbol,
        side: String(o.side || '').toUpperCase().includes('SELL') ? 'SELL' : 'BUY',
        quantity: pickNum(o.quantity, o.qty),
        price: pickNum(o.price),
        status: o.statusLabel || o.status || '--',
        open: o.open === true,
        time: o.submittedAt || o.createTime || ''
      }))
    }
  } catch { /* 未配长桥时保留空资金 */ }
}

function currentStock(symbol, market) {
  const m = String(market || 'US').toUpperCase()
  return (
    stockUniverse.value.find((x) => x.symbol === symbol && String(x.market || 'US').toUpperCase() === m)
    || activeStock.value
  )
}

function isMinuteMarketLive(market) {
  const session = getMarketSessionStatus(market)
  const mkt = String(market || '').toUpperCase()
  if (mkt === 'US') return session.sessionTag !== 'closed'
  return session.isOpen === true
}

async function loadLiveKline() {
  const s0 = activeStock.value
  if (!s0?.symbol) return
  const symbol = s0.symbol
  const market = s0.market || 'US'
  try {
    const period = currentPeriod.value === 'm5' ? '5min' : currentPeriod.value
    const apiPeriod = period === '5d' ? 'daily' : period
    const minute = isMinutePeriod(apiPeriod)
    const marketLive = isMinuteMarketLive(market)
    const usLive = String(market || '').toUpperCase() === 'US' && marketLive
    let bars = []
    let barsKind = 'ohlc'
    if (minute && marketLive) {
      const k = await getTradeQuoteKline({
        symbol,
        market,
        period: usLive && apiPeriod === 'intraday' ? '1min' : apiPeriod,
        limit: usLive ? 500 : 240
      })
      bars = k.data?.klines || k.data?.items || k.data?.bars || (Array.isArray(k.data) ? k.data : [])
      barsKind = 'minute'
    } else if (minute && !marketLive) {
      // 港股/A股收盘（及美股周末休市）不展示空分时，改走日K 时序
      const k = await getKline({
        symbol,
        market,
        period: 'daily',
        start: klineRangeFor('daily'),
        stop: 'now()'
      })
      bars = k.data?.klines || k.data?.items || k.data?.bars || (Array.isArray(k.data) ? k.data : [])
    } else {
      const k = await getKline({
        symbol,
        market,
        period: apiPeriod,
        start: klineRangeFor(period),
        stop: 'now()'
      })
      bars = k.data?.klines || k.data?.items || k.data?.bars || (Array.isArray(k.data) ? k.data : [])
    }
    const s = currentStock(symbol, market)
    if (s && Array.isArray(bars)) {
      s.liveBars = bars
      s.liveBarsKind = barsKind
      if (bars.length) {
        applyBarsToQuote(s, bars)
        if (s.price) tradeForm.value.price = Number(s.price.toFixed(2))
      }
      liveMode.value = true
    }
  } catch { /* K 线可空 */ }
}

async function loadLiveDepth() {
  const s0 = activeStock.value
  if (!s0?.symbol) return
  const symbol = s0.symbol
  const market = s0.market || 'US'
  try {
    const [depth, trades] = await Promise.all([
      getTradeQuoteDepth({ symbol, market }),
      getTradeQuoteTrades({ symbol, market, count: 20 })
    ])
    const s = currentStock(symbol, market)
    if (!s) return
    const d = depth?.data || {}
    if (Array.isArray(d.bids) && d.bids.length) s.bids = normalizeBook(d.bids, 'bid')
    if (Array.isArray(d.asks) && d.asks.length) s.asks = normalizeBook(d.asks, 'ask')
    const t = trades?.data?.trades || trades?.data || []
    if (Array.isArray(t) && t.length) s.trades = normalizeTrades(t)
    const bidVol = (s.bids || []).reduce((sum, x) => sum + (Number(x.volume) || 0), 0)
    const askVol = (s.asks || []).reduce((sum, x) => sum + (Number(x.volume) || 0), 0)
    const den = bidVol + askVol
    if (den > 0) {
      const weibi = ((bidVol - askVol) / den) * 100
      s.weibi = `${weibi >= 0 ? '+' : ''}${weibi.toFixed(2)}%`
    }
  } catch { /* 盘口可空 */ }
}

async function loadSymbolOverview() {
  const s0 = activeStock.value
  if (!s0?.symbol) return
  const symbol = s0.symbol
  const market = s0.market || 'US'
  try {
    const res = await getSymbolOverview(symbol, { market, include: 'core', history_limit: 80 })
    const s = currentStock(symbol, market)
    const data = res.data || {}
    fillIfEmpty(s, 'name', data.name)
    fillIfEmpty(s, 'category', data.fundamentals?.category)
    if (data.quote && !s.price) applyQuoteMath(s, data.quote)
    const ai = data.latestAiAnalysis
    if (ai) {
      if (s.aiScore == null && ai.confidence != null) s.aiScore = pickNum(ai.confidence, ai.finalConfidence)
      fillIfEmpty(s, 'aiVerdict', ai.finalDecision || ai.recommendation)
      fillIfEmpty(s, 'aiSummary', ai.summaryText || ai.summary)
    }
    if (s.price) tradeForm.value.price = Number(s.price.toFixed(2))
  } catch { /* 概览可空 */ }
}

async function loadBrokerSnapshot() {
  const s0 = activeStock.value
  if (!s0?.symbol) return
  const symbol = s0.symbol
  const market = s0.market || 'US'
  try {
    const res = await getTradeQuoteSnapshot({ symbol, market })
    const s = currentStock(symbol, market)
    applyBrokerSnapshot(s, res.data || res)
    stockUniverse.value = stockUniverse.value.slice()
  } catch { /* 长桥快照可空 */ }
}

async function loadRangeStats() {
  const s0 = activeStock.value
  if (!s0?.symbol) return
  const symbol = s0.symbol
  const market = s0.market || 'US'
  try {
    const k = await getKline({
      symbol,
      market,
      period: 'daily',
      start: '-1y',
      stop: 'now()',
      limit: 270
    })
    const s = currentStock(symbol, market)
    const bars = k.data?.klines || k.data?.items || k.data?.bars || (Array.isArray(k.data) ? k.data : [])
    const highs = (bars || []).map((b) => Number(b.high)).filter((n) => n > 0)
    const lows = (bars || []).map((b) => Number(b.low)).filter((n) => n > 0)
    if (highs.length) fillIfEmpty(s, 'high52', Math.max(...highs))
    if (lows.length) fillIfEmpty(s, 'low52', Math.min(...lows))
    if (highs.length) fillIfEmpty(s, 'historyHigh', Math.max(...highs))
    if (lows.length) fillIfEmpty(s, 'historyLow', Math.min(...lows))
  } catch { /* 52周可由长桥快照补 */ }
}

function guessNewsSentiment(title) {
  const t = String(title || '')
  if (/利好|大涨|超预期|买入|upgrade|beat/i.test(t)) return 'bull'
  if (/利空|大跌|下调|卖出|downgrade|miss/i.test(t)) return 'bear'
  return 'neutral'
}

async function loadSymbolNews() {
  const s = activeStock.value
  if (!s?.symbol) return
  try {
    const res = await getSymbolContent(s.symbol, {
      market: s.market || 'US',
      type: 'news',
      limit: 12
    })
    const items = res.data?.items || []
    if (!items.length) return
    s.news = items.map((n) => ({
      id: n.id || n.sourceItemId || n.title,
      title: n.title,
      source: n.sourceName || '长桥',
      time: toBeijingDisplay(n.publishedAt || n.fetchedAt, '{m}-{d} {h}:{i}') || toBeijingDisplay(n.publishedAt || n.fetchedAt),
      sentiment: guessNewsSentiment(n.title)
    }))
  } catch { /* 资讯可空 */ }
}

async function _loadLiveTape() {
  await loadLiveKline()
  loadLiveDepth()
  loadSymbolOverview()
  loadRangeStats()
  loadBrokerSnapshot()
  loadSymbolNews()
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
  nextTick(() => {
    handleResize()
  })
}

function resetSimulation() {
  if (liveMode.value) {
    Promise.all([loadLiveIndices(), loadLiveWatchlist(), loadLiveKline()]).then(() => {
      loadLiveBook()
      loadLiveDepth()
      loadSymbolOverview()
      loadRangeStats()
      loadBrokerSnapshot()
      loadSymbolNews()
      renderECharts()
      ElMessage.success('已刷新真实行情')
    })
    return
  }
  stockUniverse.value = JSON.parse(JSON.stringify(mockStockUniverse))
  ElMessage.success('行情模拟数据已重置')
  renderECharts()
}

// ====================== ECharts 图表渲染引擎 (双套主题自适应) ======================
function renderECharts() {
  if (!chartContainerRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartContainerRef.value)
  }

  const isDark = isDarkTheme()
  const themeColors = {
    bg: 'transparent',
    text: isDark ? '#9AA4B5' : '#606266',
    gridBorder: isDark ? 'rgba(148, 163, 184, 0.14)' : '#ebeef5',
    upColor: isDark ? '#f87171' : '#dc2626',
    downColor: isDark ? '#34d399' : '#059669',
    ma5: '#E5A00D',
    ma10: '#3E9BFF',
    ma20: '#A358DF',
    vwap: '#F5A524',
    tipBg: isDark ? 'rgba(15, 23, 42, 0.92)' : 'rgba(255, 255, 255, 0.95)',
    tipBorder: isDark ? 'rgba(148, 163, 184, 0.25)' : '#e4e7ed',
    tipText: isDark ? '#e2e8f0' : '#303133'
  }

  const symbol = activeStock.value.symbol

  // 分时：选「分时」时用收盘价画折线（1 分钟 OHLC 亦可）。LIVE 无分钟线时改画真实日K，禁止 mock。
  const liveIntra = currentPeriod.value === 'intraday'
    ? liveIntradayFromBars(activeStock.value.liveBars, activeStock.value.liveBarsKind)
    : null
  if (currentPeriod.value === 'intraday' && (liveIntra && liveIntra.length || !liveMode.value)) {
    const rawData = liveIntra && liveIntra.length ? liveIntra : getStockIntraday(symbol)
    const times = rawData.map(d => d.time)
    const prices = rawData.map(d => d.price)
    const avgPrices = rawData.map(d => d.avgPrice)
    const volumes = rawData.map(d => d.volume)
    const prevClose = activeStock.value.prevClose

    const option = {
      backgroundColor: themeColors.bg,
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', label: { backgroundColor: isDark ? '#232A3A' : '#e2e8f0' } },
        backgroundColor: themeColors.tipBg,
        borderColor: themeColors.tipBorder,
        textStyle: { color: themeColors.tipText, fontSize: 12 },
        formatter: params => {
          if (!params || !params.length) return ''
          const p = params[0]
          const curP = prices[p.dataIndex]
          const chg = curP - prevClose
          const chgRate = (chg / prevClose) * 100
          const avgP = avgPrices[p.dataIndex]
          const vol = volumes[p.dataIndex]
          return `
            <div style="font-weight:700;margin-bottom:4px">${times[p.dataIndex]}</div>
            <div>现价: <b style="color:${chg >= 0 ? themeColors.upColor : themeColors.downColor}">${curP.toFixed(2)} (${chg >= 0 ? '+' : ''}${chgRate.toFixed(2)}%)</b></div>
            <div>均价: <b style="color:${themeColors.vwap}">${avgP.toFixed(2)}</b></div>
            <div>分量: <b>${vol.toLocaleString()} 股</b></div>
          `
        }
      },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      grid: [
        { left: 48, right: 24, top: 16, height: '62%' },
        { left: 48, right: 24, top: '74%', height: '20%' }
      ],
      xAxis: [
        {
          type: 'category',
          data: times,
          boundaryGap: false,
          axisLine: { lineStyle: { color: themeColors.gridBorder } },
          axisLabel: { color: themeColors.text, fontSize: 11 },
          splitLine: { show: true, lineStyle: { color: themeColors.gridBorder, type: 'dashed' } }
        },
        {
          type: 'category',
          gridIndex: 1,
          data: times,
          boundaryGap: false,
          axisLine: { lineStyle: { color: themeColors.gridBorder } },
          axisLabel: { show: false },
          splitLine: { show: true, lineStyle: { color: themeColors.gridBorder, type: 'dashed' } }
        }
      ],
      yAxis: [
        {
          type: 'value',
          scale: true,
          axisLine: { show: false },
          axisLabel: { color: themeColors.text, fontSize: 11 },
          splitLine: { lineStyle: { color: themeColors.gridBorder, type: 'dashed' } }
        },
        {
          type: 'value',
          gridIndex: 1,
          scale: true,
          axisLine: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: '分时价格',
          type: 'line',
          data: prices,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.8, color: '#409EFF' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: isDark ? 'rgba(64, 158, 255, 0.3)' : 'rgba(64, 158, 255, 0.18)' },
              { offset: 1, color: 'rgba(64, 158, 255, 0.01)' }
            ])
          }
        },
        {
          name: '均价线',
          type: 'line',
          data: avgPrices,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.2, color: themeColors.vwap }
        },
        {
          name: '分时量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes.map((v, i) => ({
            value: v,
            itemStyle: {
              color: i > 0 && prices[i] >= prices[i - 1] ? themeColors.upColor : themeColors.downColor,
              opacity: 0.85
            }
          }))
        }
      ]
    }
    chartInstance.setOption(option, true)
    return
  }

  // K线模式（LIVE 无真实 bar 时宁可不画，也不用 mock 蜡烛）
  const liveK = liveKlinesFromBars(activeStock.value.liveBars)
  const klines = liveK && liveK.length
    ? liveK
    : (liveMode.value ? [] : getStockKline(symbol, currentPeriod.value))
  if (!klines.length) {
    chartInstance && chartInstance.clear()
    return
  }
  const dates = klines.map(k => axisDateLabel(k.date))
  const ohlc = klines.map(k => [k.open, k.close, k.low, k.high])
  const volumes = klines.map(k => k.volume)

  function calcMA(dayCount) {
    const result = []
    for (let i = 0; i < klines.length; i++) {
      if (i < dayCount - 1) {
        result.push('-')
        continue
      }
      let sum = 0
      for (let j = 0; j < dayCount; j++) {
        sum += klines[i - j].close
      }
      result.push(Number((sum / dayCount).toFixed(2)))
    }
    return result
  }

  const maSeries = []
  if (mainIndicators.value.includes('MA')) {
    maSeries.push({
      name: 'MA5',
      type: 'line',
      data: calcMA(5),
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1.2, color: themeColors.ma5 }
    })
    maSeries.push({
      name: 'MA10',
      type: 'line',
      data: calcMA(10),
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1.2, color: themeColors.ma10 }
    })
    maSeries.push({
      name: 'MA20',
      type: 'line',
      data: calcMA(20),
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1.2, color: themeColors.ma20 }
    })
  }

  const option = {
    backgroundColor: themeColors.bg,
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { backgroundColor: isDark ? '#232A3A' : '#e2e8f0' } },
      backgroundColor: themeColors.tipBg,
      borderColor: themeColors.tipBorder,
      textStyle: { color: themeColors.tipText, fontSize: 12 },
      formatter: params => {
        if (!params || !params.length) return ''
        const p = params[0]
        const d = klines[p.dataIndex]
        const isUp = d.close >= d.open
        return `
          <div style="font-weight:700;margin-bottom:4px">${axisDateLabel(d.date)}</div>
          <div>开: <b>${d.open}</b> 高: <b>${d.high}</b></div>
          <div>低: <b>${d.low}</b> 收: <b style="color:${isUp ? themeColors.upColor : themeColors.downColor}">${d.close}</b></div>
          <div>量: <b>${d.volume.toLocaleString()} 股</b></div>
        `
      }
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 48, right: 24, top: 16, height: '62%' },
      { left: 48, right: 24, top: '74%', height: '20%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: themeColors.gridBorder } },
        axisLabel: { color: themeColors.text, fontSize: 11 },
        splitLine: { show: true, lineStyle: { color: themeColors.gridBorder, type: 'dashed' } }
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: themeColors.gridBorder } },
        axisLabel: { show: false },
        splitLine: { show: true, lineStyle: { color: themeColors.gridBorder, type: 'dashed' } }
      }
    ],
    yAxis: [
      {
        type: 'value',
        scale: true,
        axisLine: { show: false },
        axisLabel: { color: themeColors.text, fontSize: 11 },
        splitLine: { lineStyle: { color: themeColors.gridBorder, type: 'dashed' } }
      },
      {
        type: 'value',
        gridIndex: 1,
        scale: true,
        axisLine: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: themeColors.upColor,
          color0: themeColors.downColor,
          borderColor: themeColors.upColor,
          borderColor0: themeColors.downColor
        }
      },
      ...maSeries,
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: {
            color: klines[i].close >= klines[i].open ? themeColors.upColor : themeColors.downColor,
            opacity: 0.85
          }
        }))
      }
    ]
  }
  chartInstance.setOption(option, true)
}

function handleResize() {
  chartInstance && chartInstance.resize()
}

function updateSparklines() {
  stockUniverse.value.forEach(s => {
    if (s.sparkline && s.sparkline.length) {
      s.sparkline[s.sparkline.length - 1] = s.price
    }
  })
}

// ====================== 真实行情波动模拟器 ======================
function startLiveSimulator() {
  liveTickTimer = setInterval(() => {
    stockUniverse.value.forEach(s => {
      const isTarget = s.symbol === activeSymbol.value
      const deltaPercent = (Math.random() - 0.48) * (isTarget ? 0.003 : 0.0015)
      const oldPrice = s.price
      const newPrice = Number((s.price * (1 + deltaPercent)).toFixed(3))
      s.price = newPrice
      s.change = Number((newPrice - s.prevClose).toFixed(3))
      s.changeRate = Number(((s.change / s.prevClose) * 100).toFixed(2))
      s.high = Math.max(s.high, newPrice)
      s.low = Math.min(s.low, newPrice)

      // 闪烁动效
      if (newPrice !== oldPrice) {
        priceFlashMap.value[s.symbol] = newPrice > oldPrice ? 'flash-up' : 'flash-down'
        setTimeout(() => {
          priceFlashMap.value[s.symbol] = ''
        }, 600)
      }

      if (isTarget) {
        heroFlashState.value = newPrice > oldPrice ? 'flash-up' : 'flash-down'
        setTimeout(() => {
          heroFlashState.value = ''
        }, 600)

        // 追加逐笔
        const now = new Date()
        const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
        s.trades.unshift({
          time: timeStr,
          price: newPrice,
          volume: Math.floor(Math.random() * 800 + 100),
          side: newPrice >= oldPrice ? 'buy' : 'sell'
        })
        if (s.trades.length > 25) s.trades.pop()

        // 盘口微调
        s.bids[0].price = Number((newPrice - 0.05).toFixed(2))
        s.asks[0].price = Number((newPrice + 0.05).toFixed(2))
      }
    })

    // 大盘指数微调
    marketIndices.value.forEach(idx => {
      const d = (Math.random() - 0.48) * 0.001
      idx.price = Number((idx.price * (1 + d)).toFixed(2))
    })

    updateSparklines()
  }, 2400)
}

// 监听深浅色皮肤切换，自动无缝重绘 ECharts
watch(
  () => settingsStore.isDark,
  () => {
    nextTick(() => {
      renderECharts()
    })
  }
)

function afterPaint(fn, delay = 0) {
  const run = () => window.setTimeout(fn, delay)
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(run)
  } else {
    run()
  }
}

// ====================== 生命周期 ======================
onMounted(() => {
  window.addEventListener('resize', handleResize)
  sessionTimer = setInterval(() => {
    sessionClock.value = Date.now()
  }, 30000)

  loadLiveIndices()
  loadLiveAccount()
  loadAutoTradeStatus()
  const firstKline = loadLiveKline().then(() => {
    renderECharts()
    afterPaint(() => loadBrokerSnapshot(), 50)
    afterPaint(() => loadLiveDepth(), 400)
  })
  const firstWatch = loadLiveWatchlist()

  Promise.allSettled([firstKline, firstWatch]).then(() => {
    if (!liveMode.value) {
      stockUniverse.value = JSON.parse(JSON.stringify(mockStockUniverse))
      startLiveSimulator()
      return
    }
    liveTickTimer = setInterval(() => {
      loadLiveIndices()
    }, 15000)
    bookTimer = setInterval(() => {
      if (!liveMode.value) return
      loadLiveBook()
      loadLiveKline().then(() => renderECharts())
    }, 30000)
    snapshotTimer = setInterval(() => {
      if (liveMode.value) loadBrokerSnapshot()
    }, 90000)
    newsTimer = setInterval(() => {
      if (liveMode.value) loadSymbolNews()
    }, 300000)
    afterPaint(() => loadLiveBook(), 200)
    afterPaint(() => loadSymbolNews(), 800)
  })
})

watch(rightTopTab, (tab) => {
  if (tab === 'depth' || tab === 'trades') loadLiveDepth()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (liveTickTimer) clearInterval(liveTickTimer)
  if (sessionTimer) clearInterval(sessionTimer)
  if (bookTimer) clearInterval(bookTimer)
  if (snapshotTimer) clearInterval(snapshotTimer)
  if (newsTimer) clearInterval(newsTimer)
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped lang="scss">
// 页面主容器：基于系统语义化 CSS 变量自适应浅色与深色皮肤
.pro-terminal-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 90px);
  min-height: 640px;
  background: var(--surface-soft, #f0f2f5);
  color: var(--text-emphasis, #303133);
  box-sizing: border-box;
  overflow: hidden;
  user-select: none;
  font-variant-numeric: tabular-nums;
  padding: 8px;
  gap: 6px;

  &.is-fullscreen {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    height: 100vh;
    z-index: 9999;
    padding: 8px;
  }
}

// 顶部通栏
.terminal-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--surface-card, #ffffff);
  border: 1px solid var(--border-soft, #eef2ff);
  border-radius: var(--radius-md, 8px);
  padding: 5px 10px;
  flex-shrink: 0;
  gap: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);

  .topbar-indices-wrap {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }

    .index-card-chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 11px;
      background: var(--surface-muted, #f8fafc);
      padding: 3px 8px;
      border-radius: 4px;
      border: 1px solid var(--border-soft, #eef2ff);
      white-space: nowrap;
      flex-shrink: 0;
      transition: all 0.15s ease;

      &:hover {
        background: var(--surface-hover, #eef2ff);
        transform: translateY(-1px);
      }

      .mkt-session-badge {
        font-size: 9.5px;
        font-weight: 700;
        padding: 1px 3px;
        border-radius: 2px;
        background: rgba(64, 158, 255, 0.12);
        color: #409EFF;

        &.pre { background: rgba(245, 165, 36, 0.15); color: #F5A524; }
        &.post { background: rgba(139, 92, 246, 0.15); color: #8b5cf6; }
        &.overnight { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
        &.regular { background: rgba(5, 150, 105, 0.15); color: var(--stat-down, #059669); }
        &.closed { background: rgba(144, 147, 153, 0.15); color: #909399; }
      }

      .idx-name { color: var(--text-secondary, #606266); font-weight: 500; }
      .idx-price { font-weight: 700; color: var(--text-emphasis, #303133); }

      &.up .idx-change { color: var(--stat-up, #dc2626); font-weight: 700; }
      &.down .idx-change { color: var(--stat-down, #059669); font-weight: 700; }
    }
  }

  .topbar-right-controls {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;

    .top-search-box {
      width: 220px;
    }

    .auto-trade-switch {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 6px;
      border-radius: 4px;
      background: var(--surface-muted, #f8fafc);
      border: 1px solid var(--border-soft, #eef2ff);
      flex-shrink: 0;

      &.disabled {
        opacity: 0.55;
      }

      .auto-trade-label {
        font-size: 11px;
        font-weight: 600;
        color: var(--text-secondary, #606266);
        white-space: nowrap;
      }
    }

    .cash-stat-capsule {
      display: inline-flex;
      align-items: center;
      white-space: nowrap;
      gap: 5px;
      font-size: 11px;
      background: rgba(64, 158, 255, 0.08);
      border: 1px solid rgba(64, 158, 255, 0.22);
      padding: 3px 8px;
      border-radius: 4px;
      flex-shrink: 0;

      .cash-label {
        color: var(--text-muted, #909399);
        white-space: nowrap;
      }
      .cash-amount {
        color: #409EFF;
        font-weight: 700;
        white-space: nowrap;
      }
    }

    .live-flag {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.06em;
      padding: 2px 6px;
      border-radius: 4px;
      &.on {
        color: #059669;
        background: rgba(5, 150, 105, 0.12);
      }
      &.off {
        color: #909399;
        background: rgba(144, 147, 153, 0.12);
      }
    }
  }
}

// 搜索下拉行
.search-item-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  .s-sym { font-weight: 700; }
  .s-nm { color: var(--text-muted, #909399); font-size: 11px; }
}

// 主三栏网格
.terminal-main-grid {
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr) 330px;
  flex: 1;
  min-height: 0;
  gap: 6px;
}

// 通用面板卡片
.panel-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: var(--surface-card, #ffffff);
  border: 1px solid var(--border-soft, #eef2ff);
  border-radius: var(--radius-md, 8px);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

// ====================== 左侧：自选清单 ======================
.left-pane {
  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border-soft, #eef2ff);

    .head-left {
      display: flex;
      align-items: center;
      gap: 5px;
      font-weight: 600;
      font-size: 12.5px;

      .star-icon { color: #E5A00D; font-size: 13px; }
      .count-badge {
        font-size: 9.5px;
        background: var(--surface-muted, #f8fafc);
        color: var(--text-muted, #909399);
        padding: 1px 5px;
        border-radius: 8px;
        border: 1px solid var(--border-soft, #eef2ff);
      }
    }

    .group-select-btn {
      font-size: 11.5px;
      color: #409EFF;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 2px;
    }
  }

  .watchlist-toolbar {
    padding: 5px 6px;
    border-bottom: 1px solid var(--border-soft, #eef2ff);

    .sort-actions-bar {
      display: flex;
      justify-content: space-between;
      margin-top: 5px;
      font-size: 10.5px;
      color: var(--text-muted, #909399);

      .sort-tab {
        cursor: pointer;
        padding: 1px 3px;
        border-radius: 2px;

        &:hover, &.active {
          color: #409EFF;
          font-weight: 600;
        }
      }
    }
  }

  .watchlist-body {
    flex: 1;
    overflow-y: auto;
    padding: 3px;

    .stock-row-card {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 5px 6px;
      border-radius: 4px;
      margin-bottom: 2px;
      cursor: pointer;
      transition: all 0.15s ease;
      border: 1px solid transparent;

      &:hover {
        background: var(--surface-hover, #eef2ff);
      }

      &.active {
        background: var(--surface-hover, #eef2ff);
        border-color: rgba(64, 158, 255, 0.4);
        border-left: 3px solid #409EFF;
      }

      .stock-info {
        width: 80px;
        .sym-line {
          display: flex;
          align-items: center;
          gap: 3px;
          .stock-code { font-weight: 700; font-size: 12.5px; color: var(--text-emphasis, #303133); }
          .market-badge {
            font-size: 8.5px;
            padding: 0 2px;
            border-radius: 2px;
            background: var(--surface-muted, #f8fafc);
            color: var(--text-muted, #909399);
            border: 1px solid var(--border-soft, #eef2ff);
            &.us { color: #3b82f6; }
            &.hk { color: #ec4899; }
            &.cn { color: #ef4444; }
          }
        }
        .stock-name {
          font-size: 10.5px;
          color: var(--text-secondary, #606266);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }

      .sparkline-box {
        width: 54px;
        height: 20px;
        .spark-svg { width: 100%; height: 100%; }
      }

      .price-info {
        text-align: right;
        min-width: 64px;

        .price-val {
          font-size: 12.5px;
          font-weight: 600;
          color: var(--text-emphasis, #303133);
        }

        .change-pill {
          display: inline-block;
          font-size: 10px;
          font-weight: 600;
          padding: 1px 4px;
          border-radius: 2px;
          margin-top: 1px;

          &.up {
            background: rgba(220, 38, 38, 0.12);
            color: var(--stat-up, #dc2626);
          }
          &.down {
            background: rgba(5, 150, 105, 0.12);
            color: var(--stat-down, #059669);
          }
        }
      }
    }
  }

  .watchlist-footer {
    padding: 6px 8px;
    background: var(--surface-muted, #f8fafc);
    border-top: 1px solid var(--border-soft, #eef2ff);

    .footer-stat-line {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      .lbl { color: var(--text-muted, #909399); }
      .val { font-weight: 700; }
    }

    .stat-progress-bar {
      display: flex;
      height: 3px;
      border-radius: 2px;
      overflow: hidden;
      margin: 4px 0;
      .up-seg { background: var(--stat-up, #dc2626); }
      .down-seg { background: var(--stat-down, #059669); }
    }

    .stat-sub-info {
      display: flex;
      justify-content: space-between;
      font-size: 9.5px;
      color: var(--text-muted, #909399);
    }
  }
}

// ====================== 中间：深度行情图表与多维分析 ======================
.center-pane {
  display: flex;
  flex-direction: column;
  gap: 5px;
  background: transparent;
  border: none;
  box-shadow: none;

  .ticker-board-card {
    background: var(--surface-card, #ffffff);
    border: 1px solid var(--border-soft, #eef2ff);
    border-radius: var(--radius-md, 8px);
    padding: 8px 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);

    .ticker-top-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;

      .ticker-meta-block {
        .name-line {
          display: flex;
          align-items: center;
          gap: 6px;
          .big-symbol { font-size: 20px; font-weight: 800; color: var(--text-emphasis, #303133); }
          .full-name { font-size: 14px; color: var(--text-secondary, #606266); font-weight: 600; }
          .category-tag { background: var(--surface-muted, #f8fafc); border-color: var(--border-soft, #eef2ff); font-size: 10.5px; }
          .ai-score-pill { border-radius: 10px; font-weight: 600; font-size: 10.5px; }
        }
        .sub-meta-line {
          font-size: 10.5px;
          color: var(--text-muted, #909399);
          margin-top: 2px;
          .split-dot { margin: 0 3px; }
          .status-live { color: var(--stat-down, #059669); font-weight: 600; }
        }
      }

      .ticker-price-block {
        text-align: right;
        .main-price-num {
          font-size: 24px;
          font-weight: 800;
          line-height: 1;
          .currency-unit { font-size: 11px; font-weight: 400; color: var(--text-muted, #909399); }
        }
        .chg-rate-line {
          font-size: 12px;
          font-weight: 600;
          margin-top: 2px;
          .chg-num { margin-right: 3px; }
        }
      }
    }

    .quote-metrics-grid {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 4px 8px;
      margin-top: 8px;
      padding-top: 6px;
      border-top: 1px solid var(--border-soft, #eef2ff);

      .q-cell {
        display: flex;
        justify-content: space-between;
        font-size: 10.5px;
        background: var(--el-fill-color-light, #f5f7fa);
        padding: 3px 5px;
        border-radius: 3px;
        .q-lbl { color: var(--text-muted, #909399); }
        .q-val { font-weight: 600; color: var(--text-emphasis, #303133); }
      }
    }
  }

  .chart-action-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 3px 6px;
    background: var(--surface-card, #ffffff);
    border: 1px solid var(--border-soft, #eef2ff);
    border-radius: 6px;

    .period-button-group {
      display: flex;
      gap: 3px;
      .period-toggle-btn {
        background: transparent;
        border: none;
        color: var(--text-secondary, #606266);
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 3px;
        cursor: pointer;

        &:hover, &.active {
          background: var(--surface-hover, #eef2ff);
          color: #409EFF;
          font-weight: 600;
        }
      }
    }

    .indicator-group-wrap {
      display: flex;
      align-items: center;
      .ind-lbl { font-size: 10.5px; color: var(--text-muted, #909399); margin-right: 3px; }
    }
  }

  .chart-canvas-container {
    flex: 1;
    min-height: 200px;
    background: var(--surface-card, #ffffff);
    border: 1px solid var(--border-soft, #eef2ff);
    border-radius: var(--radius-md, 8px);
    padding: 4px;
    overflow: hidden;

    .echarts-inner-dom {
      width: 100%;
      height: 100%;
      min-height: 190px;
    }
  }

  .center-bottom-drawer {
    height: 130px;
    background: var(--surface-card, #ffffff);
    border: 1px solid var(--border-soft, #eef2ff);
    border-radius: var(--radius-md, 8px);
    overflow: hidden;

    .sub-analysis-tabs {
      height: 100%;
      display: flex;
      flex-direction: column;

      :deep(.el-tabs__header) {
        margin: 0;
        background: var(--surface-muted, #f8fafc);
        border-bottom: 1px solid var(--border-soft, #eef2ff);
        padding: 0 8px;
      }

      :deep(.el-tabs__content) {
        flex: 1;
        overflow-y: auto;
        padding: 6px 10px;
      }
    }

    .tab-pill-label {
      display: flex;
      align-items: center;
      gap: 3px;
      font-size: 11.5px;
    }

    .tab-pane-ai {
      .ai-summary-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 3px;

        .verdict-badge {
          font-size: 10.5px;
          font-weight: 700;
          padding: 1px 6px;
          border-radius: 3px;
          &.bull { background: rgba(220, 38, 38, 0.12); color: var(--stat-up, #dc2626); border: 1px solid var(--stat-up, #dc2626); }
          &.neutral { background: rgba(245, 165, 36, 0.15); color: #F5A524; border: 1px solid #F5A524; }
        }
        .conf-text { font-size: 10.5px; color: var(--text-muted, #909399); }
      }

      .ai-opinion-box p {
        margin: 0 0 4px;
        font-size: 11.5px;
        color: var(--text-emphasis, #303133);
        line-height: 1.4;
      }

      .factor-chips-row {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        .factor-score-chip {
          background: var(--surface-muted, #f8fafc);
          border: 1px solid var(--border-soft, #eef2ff);
          padding: 1.5px 5px;
          border-radius: 3px;
          font-size: 10px;
          .f-lbl { color: var(--text-muted, #909399); margin-right: 3px; }
          .f-val { font-weight: 600; }
        }
      }
    }

    .tab-pane-news {
      .news-item-line {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        padding: 3px 0;
        border-bottom: 1px solid var(--border-soft, #eef2ff);

        .sentiment-pill {
          font-size: 9.5px;
          padding: 1px 3px;
          border-radius: 2px;
          &.bull { background: rgba(220, 38, 38, 0.12); color: var(--stat-up, #dc2626); }
          &.bear { background: rgba(5, 150, 105, 0.12); color: var(--stat-down, #059669); }
          &.neutral { background: var(--surface-muted, #f8fafc); color: var(--text-muted, #909399); }
        }

        .news-txt {
          flex: 1;
          color: var(--text-emphasis, #303133);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .news-src { color: var(--text-muted, #909399); font-size: 10px; }
        .news-time { color: var(--text-muted, #909399); font-size: 9.5px; }
      }
    }

    .tab-pane-flow {
      .flow-cards-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        .flow-stat-cell {
          background: var(--surface-muted, #f8fafc);
          border: 1px solid var(--border-soft, #eef2ff);
          padding: 6px;
          border-radius: 4px;
          display: flex;
          flex-direction: column;
          gap: 1px;
          .flow-lbl { font-size: 10px; color: var(--text-muted, #909399); }
          .flow-val { font-size: 12px; font-weight: 700; }
        }
      }
    }
  }
}

// ====================== 右侧：流式垂直容器 (高度滑动仅限制在右侧一栏) ======================
.right-pane {
  display: flex;
  flex-direction: column;
  gap: 6px;
  height: 100%;
  min-height: 0;
  overflow-y: auto; // 滑动完全限制在右侧一栏
  overflow-x: hidden;
  padding-right: 2px;
  scrollbar-width: thin;

  &::-webkit-scrollbar {
    width: 4px;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.3);
    border-radius: 4px;
  }

  // 1. 基本信息 / 盘口 / 逐笔 卡片 (内容自然撑开，内部绝不出现垂直滚动条)
  .depth-stream-card {
    flex-shrink: 0;
    background: var(--surface-card, #ffffff);
    border: 1px solid var(--border-soft, #eef2ff);
    border-radius: var(--radius-md, 8px);
    overflow: hidden;

    .tight-tabs {
      :deep(.el-tabs__header) {
        margin: 0;
        background: var(--surface-muted, #f8fafc);
        border-bottom: 1px solid var(--border-soft, #eef2ff);
        padding: 0 8px;
      }

      :deep(.el-tabs__content) {
        padding: 4px 6px;
        overflow: visible; // 消除内部滚动条，在原位自然撑开
      }
    }

    // 1.1 基本信息详情看板
    .stock-full-info-view {
      padding: 2px 4px;

      .info-top-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 2px;

        .info-symbol-title {
          display: flex;
          align-items: baseline;
          gap: 5px;
          .code { font-size: 14.5px; font-weight: 800; color: var(--text-emphasis, #303133); }
          .name { font-size: 12.5px; font-weight: 600; color: var(--text-secondary, #606266); }
        }

        .info-header-acts {
          display: flex;
          gap: 6px;
          font-size: 13px;
          color: var(--text-muted, #909399);
          cursor: pointer;
          .act-heart:hover, .act-heart.favorited { color: #f43f5e; }
          .act-bell:hover { color: #409EFF; }
        }
      }

      .info-hero-price-box {
        display: flex;
        align-items: baseline;
        gap: 5px;
        margin: 1px 0 2px;

        .price-main-num {
          font-size: 22px;
          font-weight: 800;
          letter-spacing: -0.5px;
        }
        .price-arrow { font-size: 15px; font-weight: 800; }
        .price-chg-val { font-size: 12.5px; font-weight: 700; }
        .price-chg-pct { font-size: 12.5px; font-weight: 700; }

        &.up { color: var(--stat-up, #dc2626); }
        &.down { color: var(--stat-down, #059669); }
      }

      .info-status-badges-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
        padding-bottom: 3px;
        border-bottom: 1px solid var(--border-soft, #eef2ff);

        .quote-time-text {
          font-size: 9.5px;
          color: var(--text-muted, #909399);
        }

        .biz-badges-group {
          display: flex;
          align-items: center;
          gap: 2px;

          .biz-badge {
            font-size: 8.5px;
            font-weight: 700;
            padding: 1px 3px;
            border-radius: 2px;
            line-height: 1;

            &.flag { font-size: 10.5px; padding: 0; }
            &.l2 { background: #3b82f6; color: #fff; }
            &.all24 { background: #2563eb; color: #fff; }
            &.margin { background: #06b6d4; color: #fff; }
            &.opt { background: #3b82f6; color: #fff; }
            &.short { background: #f97316; color: #fff; }
          }
        }
      }

      // 双列紧凑指标网格
      .info-detailed-metrics-grid {
        display: flex;
        flex-direction: column;
        gap: 2px;
        font-size: 10.5px;

        .m-row {
          display: flex;
          gap: 6px;
          justify-content: space-between;

          .m-cell {
            flex: 1;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1px 3px;
            background: var(--surface-muted, #f8fafc);
            border-radius: 2px;

            .m-lbl { color: var(--text-muted, #909399); font-size: 10px; }
            .m-val { font-weight: 600; color: var(--text-emphasis, #303133); }
          }
        }
      }

      // 展开 / 收起触发横条 (点击在原位平滑展开)
      .info-expand-toggle-bar {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-top: 4px;
        padding: 2px 0;
        cursor: pointer;
        user-select: none;

        .toggle-line {
          flex: 1;
          height: 1px;
          background: var(--border-soft, #eef2ff);
        }

        .toggle-btn-circle {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: var(--surface-card, #ffffff);
          border: 1px solid var(--border-soft, #eef2ff);
          color: var(--text-muted, #909399);
          font-size: 11px;
          transition: all 0.2s ease;
          margin: 0 6px;

          &:hover {
            color: #409EFF;
            border-color: #409EFF;
            background: var(--surface-hover, #eef2ff);
          }

          &.expanded {
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
          }
        }
      }
    }

    // 1.2 盘口样式
    .orderbook-wrap {
      font-size: 10.5px;
      padding: 2px 0;

      .order-section {
        display: flex;
        flex-direction: column;
        gap: 1px;
      }

      .book-row {
        position: relative;
        display: flex;
        justify-content: space-between;
        padding: 1px 3px;
        cursor: pointer;
        border-radius: 2px;

        &:hover { background: var(--surface-hover, #eef2ff); }

        .depth-bar-fill {
          position: absolute;
          top: 0;
          bottom: 0;
          right: 0;
          opacity: 0.15;
          pointer-events: none;
          &.ask-fill { background: var(--stat-down, #059669); }
          &.bid-fill { background: var(--stat-up, #dc2626); }
        }

        .level-tag { color: var(--text-muted, #909399); width: 28px; }
        .price-cell { font-weight: 700; width: 55px; }
        .vol-cell { text-align: right; color: var(--text-emphasis, #303133); }
      }

      .book-mid-divider {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 2px 4px;
        margin: 1px 0;
        background: var(--surface-muted, #f8fafc);
        border-radius: 3px;
        .mid-price-tag { font-size: 13px; font-weight: 800; }
        .spread-hint { font-size: 9.5px; color: var(--text-muted, #909399); }
      }
    }

    // 1.3 逐笔流水样式
    .trades-list-stream {
      font-size: 10.5px;
      height: 200px;
      overflow-y: auto;

      .stream-header-row {
        display: flex;
        justify-content: space-between;
        color: var(--text-muted, #909399);
        padding: 1px 3px;
        border-bottom: 1px solid var(--border-soft, #eef2ff);
      }
      .stream-item-row {
        display: flex;
        justify-content: space-between;
        padding: 1.5px 3px;
        .col-time { color: var(--text-muted, #909399); }
        .col-price { font-weight: 600; }
        .col-vol { color: var(--text-emphasis, #303133); }
        .col-side {
          font-size: 9px;
          padding: 0 2px;
          border-radius: 2px;
          &.side-b { background: rgba(220, 38, 38, 0.12); color: var(--stat-up, #dc2626); }
          &.side-s { background: rgba(5, 150, 105, 0.12); color: var(--stat-down, #059669); }
        }
      }
    }
  }

  // 2. 标的量化区间微卡 (压缩高度)
  .range-metric-card {
    flex-shrink: 0;
    background: var(--surface-card, #ffffff);
    border: 1px solid var(--border-soft, #eef2ff);
    border-radius: 6px;
    padding: 3px 8px;

    .range-top-info {
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: var(--text-muted, #909399);
      .r-sub { color: #409EFF; font-weight: 600; }
    }

    .range-track-bar {
      display: flex;
      align-items: center;
      gap: 4px;
      margin: 2px 0;
      font-size: 9.5px;
      color: var(--text-muted, #909399);

      .track-bg {
        flex: 1;
        height: 3px;
        background: var(--surface-muted, #f8fafc);
        border: 1px solid var(--border-soft, #eef2ff);
        border-radius: 2px;
        position: relative;

        .track-dot {
          position: absolute;
          top: -2.5px;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #409EFF;
          border: 1.5px solid #fff;
          transform: translateX(-50%);
        }
      }
    }

    .range-extra-info {
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: var(--text-muted, #909399);
      strong { color: var(--text-emphasis, #303133); }
    }
  }

  // 3. 快捷交易下单面板 (大幅压缩高度与间距)
  .quick-trade-card {
    flex-shrink: 0;
    background: var(--surface-card, #ffffff);
    border: 1px solid var(--border-soft, #eef2ff);
    border-radius: var(--radius-md, 8px);
    padding: 5px 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;

    .trade-side-switcher {
      display: flex;
      gap: 3px;

      .side-btn {
        flex: 1;
        padding: 4px 0;
        border-radius: 4px;
        border: 1px solid transparent;
        font-weight: 700;
        font-size: 11.5px;
        cursor: pointer;
        background: var(--surface-muted, #f8fafc);
        color: var(--text-secondary, #606266);

        &.buy-btn.active {
          background: var(--stat-up, #dc2626);
          color: #fff;
        }

        &.sell-btn.active {
          background: var(--stat-down, #059669);
          color: #fff;
        }
      }
    }

    .form-item-line {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;

      .f-lbl {
        font-size: 10.5px;
        color: var(--text-muted, #909399);
        width: 28px;
      }

      .stepper-wrap {
        flex: 1;
        display: flex;
        gap: 3px;
        .fill-latest-btn {
          background: var(--surface-muted, #f8fafc);
          border: 1px solid var(--border-soft, #eef2ff);
          color: #409EFF;
          font-size: 10px;
          border-radius: 3px;
          padding: 0 6px;
          cursor: pointer;
        }
      }
    }

    .ratio-pill-row {
      display: flex;
      gap: 3px;

      .r-pill {
        flex: 1;
        padding: 1.5px 0;
        background: var(--surface-muted, #f8fafc);
        border: 1px solid var(--border-soft, #eef2ff);
        color: var(--text-secondary, #606266);
        font-size: 10px;
        border-radius: 3px;
        cursor: pointer;

        &:hover {
          background: var(--surface-hover, #eef2ff);
          color: #409EFF;
        }
      }
    }

    .trade-cost-summary {
      background: var(--surface-muted, #f8fafc);
      border: 1px solid var(--border-soft, #eef2ff);
      padding: 4px 6px;
      border-radius: 3px;
      font-size: 10.5px;

      .cost-line {
        display: flex;
        justify-content: space-between;
        color: var(--text-muted, #909399);
        .cost-val { color: var(--text-emphasis, #303133); font-size: 11.5px; }
      }
      .cost-sub-line {
        display: flex;
        justify-content: space-between;
        font-size: 9.5px;
        color: var(--text-muted, #909399);
        margin-top: 1px;
      }
    }

    .do-order-btn {
      width: 100%;
      height: 26px;
      font-weight: 700;
      border: none;
      font-size: 11.5px;
      padding: 0;

      &.btn-order-buy {
        background: var(--stat-up, #dc2626);
        color: #fff;
      }

      &.btn-order-sell {
        background: var(--stat-down, #059669);
        color: #fff;
      }
    }
  }

  // 4. 当日委托/持仓小型监控
  .bottom-orders-card {
    flex-shrink: 0;
    min-height: 90px;
    background: var(--surface-card, #ffffff);
    border: 1px solid var(--border-soft, #eef2ff);
    border-radius: var(--radius-md, 8px);
    overflow: hidden;

    .tight-tabs {
      :deep(.el-tabs__header) {
        margin: 0;
        background: var(--surface-muted, #f8fafc);
        border-bottom: 1px solid var(--border-soft, #eef2ff);
        padding: 0 8px;
      }

      :deep(.el-tabs__content) {
        padding: 2px 4px;
      }
    }

    .orders-scroll-list, .positions-scroll-list {
      font-size: 10.5px;
      .order-item-card, .pos-item-card {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 2px 3px;
        border-bottom: 1px solid var(--border-soft, #eef2ff);
        cursor: pointer;

        &:hover { background: var(--surface-hover, #eef2ff); }

        .o-main, .p-main {
          display: flex;
          align-items: center;
          gap: 3px;
          .o-side-badge { font-weight: 700; font-size: 10px; }
          .o-code, .p-code { font-weight: 600; color: var(--text-emphasis, #303133); }
          .o-detail, .p-qty { color: var(--text-muted, #909399); font-size: 10px; }
        }

        .p-stat {
          text-align: right;
          .p-val { color: var(--text-secondary, #606266); font-size: 10px; }
          .p-pnl { font-weight: 600; font-size: 10px; }
        }
      }

      .empty-hint-text {
        text-align: center;
        color: var(--text-muted, #909399);
        padding: 10px 0;
        font-size: 10.5px;
      }
    }
  }
}

// ====================== 语义化色彩与跳动动效 ======================
.up { color: var(--stat-up, #dc2626) !important; }
.down { color: var(--stat-down, #059669) !important; }
.flat { color: var(--text-muted, #909399) !important; }
.font-bold { font-weight: 700; }

@keyframes flashGreen {
  0% { background-color: rgba(5, 150, 105, 0.25); }
  100% { background-color: transparent; }
}

@keyframes flashRed {
  0% { background-color: rgba(220, 38, 38, 0.25); }
  100% { background-color: transparent; }
}

.flash-up {
  animation: flashRed 0.6s ease-out;
}

.flash-down {
  animation: flashGreen 0.6s ease-out;
}

// 窄屏自适应
@media (max-width: 1200px) {
  .terminal-main-grid {
    grid-template-columns: 240px minmax(0, 1fr) 300px;
  }
}
</style>
