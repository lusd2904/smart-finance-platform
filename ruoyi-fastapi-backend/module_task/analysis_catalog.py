"""
自动分析定时任务目录。

页面与调度微服务共用这份清单；sys_job 存 cron/启停，这里存业务含义。
系统自带的 scheduler_test 演示任务不纳入。
"""

from __future__ import annotations

from dataclasses import dataclass

CRON_MIN_FIELDS = 6


@dataclass(frozen=True)
class AnalysisJobSpec:
    job_id: int
    code: str
    category: str
    title: str
    description: str
    invoke_target: str
    default_cron: str
    schedule_label: str
    heavy: bool
    queue_type: str | None
    default_status: str


CATEGORY_LABELS = {
    'market': '行情',
    'quant': '量化',
    'sentiment': '舆情',
    'trade': '交易',
}

ANALYSIS_JOBS: tuple[AnalysisJobSpec, ...] = (
    AnalysisJobSpec(
        job_id=100,
        code='sentiment_collect',
        category='sentiment',
        title='舆情采集与AI分析',
        description='采集财经资讯并调用模型给出美/港/A 影响研判。',
        invoke_target='module_task.sentiment_task.collect_and_analyze_job',
        default_cron='0 0/10 * * * ?',
        schedule_label='每 10 分钟',
        heavy=True,
        queue_type='sentiment_collect',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=101,
        code='market_sync',
        category='market',
        title='行情数据每日同步',
        description='收盘后增量同步目标标的近十年行情到 InfluxDB。',
        invoke_target='module_task.market_task.sync_market_job',
        default_cron='0 30 5 * * ?',
        schedule_label='每天 05:30',
        heavy=True,
        queue_type='market_sync',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=102,
        code='quant_strategy',
        category='quant',
        title='量化策略每日运行',
        description='对自选池按策略档位扫描并生成买卖信号。',
        invoke_target='module_task.quant_task.run_strategy_job',
        default_cron='0 0 6 * * ?',
        schedule_label='每天 06:00',
        heavy=True,
        queue_type='strategy_run',
        default_status='1',
    ),
    AnalysisJobSpec(
        job_id=103,
        code='finance_briefings',
        category='market',
        title='财经资讯简报刷新',
        description='聚合内部简报与外部新闻，写入财经资讯流。',
        invoke_target='module_task.market_task.refresh_finance_briefings_job',
        default_cron='0 15 * * * ?',
        schedule_label='每小时第 15 分钟',
        heavy=False,
        queue_type='finance_briefings',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=104,
        code='symbol_content',
        category='market',
        title='标的内容缓存刷新',
        description='刷新热门标的公告、资讯与讨论缓存，需长桥凭证。',
        invoke_target='module_task.market_task.refresh_symbol_content_job',
        default_cron='0 0/30 * * * ?',
        schedule_label='每 30 分钟',
        heavy=False,
        queue_type='symbol_content',
        default_status='1',
    ),
    AnalysisJobSpec(
        job_id=105,
        code='factor_scan',
        category='quant',
        title='全市场因子日扫',
        description='收盘后计算 Alpha101/158 与八大因子族，写入读模型快照。',
        invoke_target='module_task.quant_task.run_daily_factor_scan_job',
        default_cron='0 10 6 * * ?',
        schedule_label='每天 06:10',
        heavy=True,
        queue_type='factor_scan',
        default_status='1',
    ),
    AnalysisJobSpec(
        job_id=106,
        code='position_monitor',
        category='quant',
        title='持仓止损监控',
        description='检查持仓浮亏，超阈值写入风控事件。',
        invoke_target='module_task.quant_task.run_position_monitor_job',
        default_cron='0 0/10 * * * ?',
        schedule_label='每 10 分钟',
        heavy=False,
        queue_type='position_monitor',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=107,
        code='indicator_refresh',
        category='quant',
        title='行情指标快照刷新',
        description='刷新目标池最新价与涨跌快照，供看板首屏读取。',
        invoke_target='module_task.quant_task.run_indicator_refresh_job',
        default_cron='0 0/15 * * * ?',
        schedule_label='每 15 分钟',
        heavy=True,
        queue_type='indicator_refresh',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=108,
        code='factor_qc',
        category='quant',
        title='因子质检 IC/IR',
        description='对股票池做截面 IC/IR 与五分位收益质检。',
        invoke_target='module_task.quant_task.run_factor_qc_job',
        default_cron='0 40 6 * * ?',
        schedule_label='每天 06:40',
        heavy=True,
        queue_type='factor_qc',
        default_status='1',
    ),
    AnalysisJobSpec(
        job_id=109,
        code='watchlist_analyze',
        category='market',
        title='自选清单小时分析',
        description='综合技术指标、长桥资讯与舆情，对行情自选给出建议。',
        invoke_target='module_task.market_task.analyze_watchlist_job',
        default_cron='0 20 * * * ?',
        schedule_label='每小时第 20 分钟',
        heavy=True,
        queue_type='watchlist_analyze',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=112,
        code='auto_trade_scan',
        category='trade',
        title='自动交易扫描',
        description='全局调度：扫描美/港热度 Top50（叠加各账户美/港自选）。A 股不扫。是否真实下单由该账户自动交易开关决定。',
        invoke_target='module_task.trade_task.run_auto_trade_scan_job',
        default_cron='0 0/15 * * * ?',
        schedule_label='每 15 分钟',
        heavy=True,
        queue_type='auto_trade_scan',
        default_status='1',
    ),
    AnalysisJobSpec(
        job_id=113,
        code='market_heat_cn',
        category='market',
        title='A股收盘热度采集',
        description='A股收盘后拉取指数/成交额/A-D 并生成 Top50 快照。',
        invoke_target='module_task.market_task.collect_market_heat_cn_job',
        default_cron='0 5 7 * * ?',
        schedule_label='每天 07:05',
        heavy=True,
        queue_type='market_heat_collect',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=114,
        code='market_heat_hk',
        category='market',
        title='港股收盘热度采集',
        description='港股收盘后拉取指数/成交额/A-D 并生成 Top50 快照。',
        invoke_target='module_task.market_task.collect_market_heat_hk_job',
        default_cron='0 5 8 * * ?',
        schedule_label='每天 08:05',
        heavy=True,
        queue_type='market_heat_collect',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=115,
        code='market_heat_us',
        category='market',
        title='美股收盘热度采集',
        description='美股收盘后拉取指数/成交额/A-D 并生成 Top50 快照。',
        invoke_target='module_task.market_task.collect_market_heat_us_job',
        default_cron='0 5 21 * * ?',
        schedule_label='每天 21:05',
        heavy=True,
        queue_type='market_heat_collect',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=116,
        code='daily_list_scan',
        category='quant',
        title='收盘后扫描次日策略清单',
        description='A股收盘后扫描策略结果，生成下一交易日清单；非交易日/空结果跳过。',
        invoke_target='module_task.quant_task.run_daily_list_scan_job',
        default_cron='0 20 7 * * ?',
        schedule_label='每天 07:20',
        heavy=True,
        queue_type='daily_list_scan',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=117,
        code='feishu_push',
        category='trade',
        title='飞书策略摘要推送',
        description='按用户时区与交易日历推送次日策略摘要到飞书个人/群。',
        invoke_target='module_task.trade_task.run_feishu_push_job',
        default_cron='0 0/5 * * * ?',
        schedule_label='每 5 分钟',
        heavy=False,
        queue_type='feishu_push',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=118,
        code='daily_list_open',
        category='trade',
        title='开盘执行排队模拟单',
        description='A股开盘后把排队的长桥模拟开仓送到券商。',
        invoke_target='module_task.quant_task.run_daily_list_open_job',
        default_cron='0 31 1 * * ?',
        schedule_label='每天 01:31',
        heavy=True,
        queue_type='daily_list_open',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=119,
        code='stock_pick_run',
        category='market',
        title='全市场智能选股',
        description='结合指标、舆情与开盘指数生成选股单；休市市场自动去掉指数。可在本页改 cron。',
        invoke_target='module_task.market_task.run_stock_pick_job',
        default_cron='0 50 7,8,21 * * ?',
        schedule_label='每天 15:50 / 16:50 / 05:50 北京时间（容器 UTC）',
        heavy=True,
        queue_type='stock_pick_run',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=121,
        code='eod_kline_cn',
        category='market',
        title='A股收盘拉日K与分时',
        description='15:00 收盘后增量日K，并拉取精选/Top50 当日分时写入时序库。',
        invoke_target='module_task.market_task.eod_kline_sync_cn_job',
        default_cron='0 25 7 * * ?',
        schedule_label='每天 15:25 北京时间',
        heavy=True,
        queue_type='eod_kline_sync',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=122,
        code='eod_kline_hk',
        category='market',
        title='港股收盘拉日K与分时',
        description='16:00 收盘后增量日K，并拉取精选/Top50 当日分时写入时序库。',
        invoke_target='module_task.market_task.eod_kline_sync_hk_job',
        default_cron='0 25 8 * * ?',
        schedule_label='每天 16:25 北京时间',
        heavy=True,
        queue_type='eod_kline_sync',
        default_status='0',
    ),
    AnalysisJobSpec(
        job_id=123,
        code='eod_kline_us',
        category='market',
        title='美股收盘拉日K与分时',
        description='美股 16:00 ET 收盘后（北京时间约 05:25）增量日K + 分时。',
        invoke_target='module_task.market_task.eod_kline_sync_us_job',
        default_cron='0 25 21 * * ?',
        schedule_label='每天 05:25 北京时间',
        heavy=True,
        queue_type='eod_kline_sync',
        default_status='0',
    ),
)

ANALYSIS_JOB_MAP = {item.job_id: item for item in ANALYSIS_JOBS}
ANALYSIS_INVOKE_TARGETS = {item.invoke_target for item in ANALYSIS_JOBS}


def humanize_cron(expr: str | None) -> str:
    """把 Quartz 风格 6/7 段 cron 转成可读中文。"""
    parts = str(expr or '').split()
    if len(parts) < CRON_MIN_FIELDS:
        return expr or '--'
    _second, minute, hour, day, _month, _week = parts[:CRON_MIN_FIELDS]
    day_any = day in {'*', '?'}

    def _step(field: str) -> int | None:
        if '/' not in field:
            return None
        try:
            return int(field.split('/', 1)[1])
        except ValueError:
            return None

    minute_step = _step(minute)
    hour_step = _step(hour)
    if minute_step and hour == '*' and day_any:
        start = minute.split('/', 1)[0]
        if start not in {'0', '*', ''}:
            return f'每 {minute_step} 分钟（从第 {start} 分钟）'
        return f'每 {minute_step} 分钟'
    if hour_step and day_any and minute in {'0', '00'}:
        return f'每 {hour_step} 小时'
    if hour.isdigit() and minute.isdigit() and day_any:
        return f'每天 {int(hour):02d}:{int(minute):02d}'
    if hour == '*' and minute.isdigit() and day_any:
        return f'每小时第 {int(minute)} 分钟'
    return expr or '--'


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category)
