import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import CrudResponseModel, PageModel
from exceptions.exception import ServiceException
from module_ai.constant.ai_model_resolve import GROK46_MODEL_CODES, select_ai_model_row
from module_ai.dao.ai_model_dao import AiModelDao
from module_ai.entity.do.ai_model_do import AiModels
from module_market.service.index_quotes_service import MarketIndexService, list_session_status
from module_sentiment.dao.sentiment_dao import SentimentAiConfigDao, SentimentAnalysisDao, SentimentNewsDao
from module_sentiment.entity.vo.sentiment_vo import (
    DeleteSentimentNewsModel,
    SentimentAiConfigModel,
    SentimentAnalysisModel,
    SentimentAnalysisPageQueryModel,
    SentimentNewsPageQueryModel,
)
from module_sentiment.service.analyzer_service import (
    GATEWAY_FAILOVER_CODES,
    HTTP_TOO_MANY_REQUESTS,
    SentimentAiAnalyzer,
)
from module_sentiment.service.collector_service import SentimentCollector
from utils.common_util import CamelCaseUtil
from utils.crypto_util import CryptoUtil
from utils.log_util import logger
from utils.time_format_util import apply_beijing_times, format_beijing_datetime, now_beijing


class SentimentService:
    """
    舆情分析模块服务层
    """

    ANALYZE_WINDOW_MINUTES = 10
    MAX_NEWS_SAFETY_CAP = 200

    @staticmethod
    def _is_complete_model(model: AiModels) -> bool:
        return bool(model.base_url and model.api_key and model.model_code)

    @classmethod
    def _is_gateway_failover_code(cls, code: int | None) -> bool:
        return code in GATEWAY_FAILOVER_CODES

    @classmethod
    async def _list_sentiment_ai_candidates(cls, query_db: AsyncSession) -> list[AiModels]:
        rows = (
            (
                await query_db.execute(
                    select(AiModels)
                    .where(AiModels.status == '0')
                    .order_by(AiModels.model_sort, AiModels.model_id)
                )
            )
            .scalars()
            .all()
        )
        complete = [model for model in rows if cls._is_complete_model(model)]
        if not complete:
            return []
        primary = select_ai_model_row(complete, 'sentiment', GROK46_MODEL_CODES)
        ordered: list[AiModels] = []
        seen: set[int] = set()
        if primary and primary.model_id is not None:
            ordered.append(primary)
            seen.add(int(primary.model_id))
        for model in complete:
            model_id = model.model_id
            if model_id is None or int(model_id) in seen:
                continue
            ordered.append(model)
            seen.add(int(model_id))
        return ordered

    @staticmethod
    def _model_runtime_config(model: AiModels) -> dict[str, Any]:
        api_key = CryptoUtil.decrypt(model.api_key) or ''
        return {
            'baseUrl': model.base_url or '',
            'apiKey': api_key,
            'modelName': model.model_code or '',
            'temperature': model.temperature if model.temperature is not None else 0.2,
        }

    # ---------- 资讯 ----------

    @classmethod
    async def get_news_list_services(
        cls, query_db: AsyncSession, query_object: SentimentNewsPageQueryModel, is_page: bool = True
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取舆情资讯分页列表service
        """
        return apply_beijing_times(await SentimentNewsDao.get_news_list(query_db, query_object, is_page))

    @classmethod
    async def delete_news_services(
        cls, query_db: AsyncSession, page_object: DeleteSentimentNewsModel
    ) -> CrudResponseModel:
        """
        删除舆情资讯service
        """
        if not page_object.news_ids:
            raise ServiceException(message='传入资讯id为空')
        news_id_list = [int(i) for i in page_object.news_ids.split(',') if i]
        try:
            await SentimentNewsDao.delete_news_dao(query_db, news_id_list)
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def get_stats_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        """
        获取舆情统计数据service
        """
        stats = await SentimentNewsDao.count_news(query_db)
        latest = await SentimentAnalysisDao.get_latest_analysis(query_db)
        stats['latestAnalysis'] = (
            SentimentAnalysisModel(**CamelCaseUtil.transform_result(latest)).model_dump(by_alias=True)
            if latest
            else None
        )
        return apply_beijing_times(stats)

    # ---------- 采集 ----------

    @classmethod
    async def collect_news_services(cls, query_db: AsyncSession) -> dict[str, int]:
        """
        执行一次舆情采集（入库去重）service

        :return: {'fetched': 抓取条数, 'saved': 新入库条数}
        """
        try:
            config = await cls.get_ai_config_services(query_db)
            sources = (config.enabled_sources or 'eastmoney,sina,ths,wallstreetcn,google_news').split(',')
            news_list = await SentimentCollector.collect(sources)
        except Exception as exc:
            logger.warning(f'[舆情采集] 采集降级为空列表: {exc}')
            return {
                'fetched': 0,
                'saved': 0,
                'message': '资讯源暂时不可用（超时或限流），已返回空列表，请稍后重试',
            }
        if not news_list:
            return {
                'fetched': 0,
                'saved': 0,
                'message': '资讯源暂无新内容或上游不可用，已返回空列表',
            }
        hashes = [n['uniq_hash'] for n in news_list]
        existing = await SentimentNewsDao.get_existing_hashes(query_db, hashes)
        fresh = [n for n in news_list if n['uniq_hash'] not in existing]
        for n in fresh:
            n['analyzed'] = '0'
            n['create_time'] = now_beijing()
        try:
            if fresh:
                await SentimentNewsDao.add_news_batch(query_db, fresh)
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            raise e
        logger.info(f'[舆情采集] 抓取 {len(news_list)} 条，新入库 {len(fresh)} 条')
        return {'fetched': len(news_list), 'saved': len(fresh)}

    # ---------- AI配置 ----------

    @classmethod
    async def get_ai_config_services(cls, query_db: AsyncSession) -> SentimentAiConfigModel:
        """
        获取AI配置service

        AI连接参数(base_url/api_key/model_name/temperature)统一存储在ai_models(scope='sentiment')，
        舆情特有的业务参数(max_news_per_round/auto_analyze/enabled_sources)仍存储在sentiment_ai_config，
        此处合并两部分数据，保持接口返回结构与迁移前一致
        """
        # 统一从 AI 模型管理解析：sentiment -> grok-4.6 -> global -> chat -> 任意可用模型
        ai_model = await AiModelDao.resolve_ai_model_for_business(
            query_db, 'sentiment', preferred_codes=GROK46_MODEL_CODES
        )
        ext_config = await SentimentAiConfigDao.get_config(query_db)

        if ai_model:
            base_url = ai_model.base_url or ''
            api_key = CryptoUtil.decrypt(ai_model.api_key) or ''
            model_name = ai_model.model_code or ''
            temperature = ai_model.temperature if ai_model.temperature is not None else 0.2
        else:
            base_url, api_key, model_name, temperature = '', '', '', 0.2

        if ext_config:
            max_news_per_round = ext_config.max_news_per_round
            auto_analyze = ext_config.auto_analyze
            enabled_sources = ext_config.enabled_sources
        else:
            max_news_per_round, auto_analyze, enabled_sources = (
                200,
                '1',
                'eastmoney,sina,ths,wallstreetcn,google_news',
            )

        return SentimentAiConfigModel(
            configId=ext_config.config_id if ext_config else None,
            baseUrl=base_url,
            apiKey=api_key,
            modelName=model_name,
            temperature=temperature,
            maxNewsPerRound=max_news_per_round,
            autoAnalyze=auto_analyze,
            enabledSources=enabled_sources,
            updateBy=ext_config.update_by if ext_config else None,
            updateTime=ext_config.update_time if ext_config else None,
            # 只读：展示当前实际复用的模型来源 scope，避免重复维护两套 Key
            modelScope=getattr(ai_model, 'scope', None) if ai_model else None,
            modelId=getattr(ai_model, 'model_id', None) if ai_model else None,
        )

    @classmethod
    async def save_ai_config_services(
        cls, query_db: AsyncSession, config: SentimentAiConfigModel, update_by: str
    ) -> CrudResponseModel:
        """
        保存AI配置service

        拆分持久化：AI连接参数(base_url/api_key/model_name->model_code/temperature)写入
        ai_models(scope='sentiment')（api_key加密存储，与AI模型管理页保持一致）；
        舆情业务参数(max_news_per_round/auto_analyze/enabled_sources)仍写入sentiment_ai_config
        """
        # 连接参数统一在「AI 管理-模型管理」维护；此处只保存舆情业务参数
        config_dict = config.model_dump(
            exclude_unset=True,
            exclude={'config_id', 'base_url', 'api_key', 'model_name', 'temperature', 'model_scope', 'model_id'},
        )
        now = now_beijing()
        ext_values = config_dict
        ext_values['update_by'] = update_by
        ext_values['update_time'] = now

        try:
            await SentimentAiConfigDao.save_config(query_db, ext_values)
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='保存成功（模型连接请在 AI 管理中配置）')
        except Exception as e:
            await query_db.rollback()
            raise e

    # ---------- 分析 ----------

    @classmethod
    async def get_analysis_list_services(
        cls, query_db: AsyncSession, query_object: SentimentAnalysisPageQueryModel, is_page: bool = True
    ) -> PageModel | list[dict[str, Any]]:
        """
        获取分析结果分页列表service
        """
        return apply_beijing_times(await SentimentAnalysisDao.get_analysis_list(query_db, query_object, is_page))

    @classmethod
    async def get_analysis_detail_services(cls, query_db: AsyncSession, analysis_id: int) -> SentimentAnalysisModel:
        """
        获取分析结果详情service
        """
        analysis = await SentimentAnalysisDao.get_analysis_by_id(query_db, analysis_id)
        return SentimentAnalysisModel(**CamelCaseUtil.transform_result(analysis)) if analysis else SentimentAnalysisModel()

    @classmethod
    async def get_analysis_trend_services(cls, query_db: AsyncSession, limit: int = 24) -> list[dict[str, Any]]:
        """
        获取近期分析趋势（用于图表）service。
        缺失市场分保持 None，不填 0；前端折线用 connectNulls 跨点相连。
        """
        rows = await SentimentAnalysisDao.get_recent_analysis(query_db, limit)
        rows.reverse()
        return [
            {
                'analysisId': r.analysis_id,
                'createTime': format_beijing_datetime(r.create_time, '%m-%d %H:%M') if r.create_time else '',
                'usScore': r.us_score,
                'hkScore': r.hk_score,
                'aScore': r.a_score,
            }
            for r in rows
        ]

    @staticmethod
    def _normalize_direction(direction: str | None) -> str:
        if not direction:
            return ''
        d = str(direction).lower()
        if any(token in d for token in ('多', 'bull', 'up', '涨', 'positive')):
            return 'up'
        if any(token in d for token in ('空', 'bear', 'down', '跌', 'negative')):
            return 'down'
        return 'flat'

    @staticmethod
    def _parse_risk_events(raw: str | list | None) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, list):
            return [item if isinstance(item, str) else str(item) for item in raw]
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [item if isinstance(item, str) else str(item) for item in parsed]
        except Exception:
            pass
        return [part.strip() for part in re.split(r'[\n;；]', str(raw)) if part.strip()]

    @classmethod
    def _market_cards(cls, latest: dict[str, Any]) -> list[dict[str, Any]]:
        specs = (
            ('us', '美股三大指数', 'usDirection', 'usScore', 'usReason'),
            ('hk', '港股指数', 'hkDirection', 'hkScore', 'hkReason'),
            ('a', 'A股指数', 'aDirection', 'aScore', 'aReason'),
        )
        markets: list[dict[str, Any]] = []
        for key, name, direction_key, score_key, reason_key in specs:
            direction = latest.get(direction_key)
            markets.append(
                {
                    'key': key,
                    'name': name,
                    'direction': direction,
                    'directionNorm': cls._normalize_direction(direction),
                    'score': latest.get(score_key),
                    'reason': latest.get(reason_key),
                }
            )
        return markets

    @classmethod
    async def get_widget_dashboard_services(cls, query_db: AsyncSession, trend_limit: int = 24) -> dict[str, Any]:
        """
        聚合舆情大盘数据，供 macOS Widget 等只读客户端使用。
        """
        limit = max(1, min(int(trend_limit or 24), 100))
        stats = await cls.get_stats_services(query_db)
        latest_row: dict[str, Any] = {}
        page = await cls.get_analysis_list_services(
            query_db,
            SentimentAnalysisPageQueryModel(page_num=1, page_size=1, status='0'),
            is_page=True,
        )
        page_rows = getattr(page, 'rows', None) or []
        if page_rows:
            first = page_rows[0]
            latest_row = first if isinstance(first, dict) else dict(first)
        elif stats.get('latestAnalysis') and isinstance(stats['latestAnalysis'], dict):
            latest_row = stats['latestAnalysis']

        trend_rows = await SentimentAnalysisDao.get_recent_analysis(query_db, limit)
        trend_rows.reverse()
        trend = [
            {
                'createTime': format_beijing_datetime(row.create_time),
                'usScore': row.us_score,
                'hkScore': row.hk_score,
                'aScore': row.a_score,
            }
            for row in trend_rows
        ]

        updated_at = latest_row.get('createTime') or format_beijing_datetime(now_beijing())
        summary = latest_row.get('summary') or ''
        risk_events = cls._parse_risk_events(latest_row.get('riskEvents'))

        widget_latest = {
            key: latest_row.get(key)
            for key in (
                'analysisId',
                'createTime',
                'summary',
                'usDirection',
                'usScore',
                'usReason',
                'hkDirection',
                'hkScore',
                'hkReason',
                'aDirection',
                'aScore',
                'aReason',
                'riskEvents',
                'modelName',
                'status',
            )
            if key in latest_row
        }

        sessions = list_session_status()
        indexes: list[dict[str, Any]] = []
        indexes_as_of = format_beijing_datetime(now_beijing())
        indexes_cached = False
        try:
            quotes_data = await MarketIndexService.get_in_session_quotes()
            indexes = quotes_data.get('items') or []
            indexes_as_of = quotes_data.get('asOf') or indexes_as_of
            indexes_cached = bool(quotes_data.get('cached'))
        except Exception as exc:
            logger.warning(f'[widget-dashboard] 大盘指数拉取失败，已降级为空: {exc}')

        return apply_beijing_times(
            {
                'updatedAt': updated_at,
                'stats': {
                    'total': stats.get('total', 0),
                    'today': stats.get('today', 0),
                    'unanalyzed': stats.get('unanalyzed', 0),
                },
                'markets': cls._market_cards(latest_row),
                'summary': summary,
                'riskEvents': risk_events,
                'latest': widget_latest,
                'trend': trend,
                'indexes': indexes,
                'indexesAsOf': indexes_as_of,
                'indexesCached': indexes_cached,
                'sessions': sessions,
            }
        )

    @classmethod
    async def run_analysis_services(cls, query_db: AsyncSession) -> dict[str, Any]:  # noqa: PLR0912
        """
        对未分析的资讯执行一次AI大盘影响分析service

        :return: {'analyzed': 条数, 'analysisId': int|None, 'message': str}
        """
        config = await cls.get_ai_config_services(query_db)
        candidates = await cls._list_sentiment_ai_candidates(query_db)
        if not candidates:
            raise ServiceException(message='请先在AI配置中填写Base URL、API Key与模型名称')
        limit = min(int(config.max_news_per_round or cls.MAX_NEWS_SAFETY_CAP), cls.MAX_NEWS_SAFETY_CAP)
        news_rows = await SentimentNewsDao.get_unanalyzed_news(
            query_db, limit, window_minutes=cls.ANALYZE_WINDOW_MINUTES
        )
        if not news_rows:
            return {
                'analyzed': 0,
                'analysisId': None,
                'message': f'最近 {cls.ANALYZE_WINDOW_MINUTES} 分钟内暂无待分析的舆情资讯',
            }
        news_list = [
            {
                'news_id': r.news_id,
                'source': r.source,
                'title': r.title,
                'content': (r.content or '')[:800],
                'pub_time': r.pub_time.strftime('%Y-%m-%d %H:%M') if r.pub_time else '',
            }
            for r in news_rows
        ]
        ai_result: dict[str, Any] | None = None
        used_model_name = ''
        for model in candidates:
            runtime = cls._model_runtime_config(model)
            if not (runtime['baseUrl'] and runtime['apiKey'] and runtime['modelName']):
                continue
            ai_result = await SentimentAiAnalyzer.analyze(
                base_url=runtime['baseUrl'],
                api_key=runtime['apiKey'],
                model_name=runtime['modelName'],
                news_list=news_list,
                temperature=runtime['temperature'],
            )
            used_model_name = runtime['modelName']
            if ai_result.get('ok'):
                break
            if ai_result.get('code') == HTTP_TOO_MANY_REQUESTS:
                break
            if not cls._is_gateway_failover_code(ai_result.get('code')):
                break
            logger.warning(
                f'[舆情分析] 模型 {runtime["modelName"]} 网关 {ai_result.get("code")}，尝试下一模型'
            )
        if ai_result is None:
            raise ServiceException(message='未找到可用的 AI 模型配置')
        if ai_result.get('code') == HTTP_TOO_MANY_REQUESTS:
            return {
                'analyzed': 0,
                'analysisId': None,
                'rateLimited': True,
                'retryAfter': ai_result.get('retryAfter') or 60,
                'message': 'AI 分析触发限流，请稍后再试，不要连续点击',
            }
        news_ids = [n['news_id'] for n in news_list]
        analysis_record: dict[str, Any] = {
            'news_count': len(news_ids),
            'news_ids': ','.join(str(i) for i in news_ids),
            'model_name': used_model_name or config.model_name,
            'raw_response': (ai_result.get('raw') or '')[:60000],
            'create_time': now_beijing(),
        }
        if ai_result['ok']:
            result = ai_result['result']
            us, hk, a = result.get('us') or {}, result.get('hk') or {}, result.get('a') or {}
            analysis_record.update(
                {
                    'summary': result.get('summary'),
                    'us_direction': us.get('direction'),
                    'us_score': us.get('score'),
                    'us_reason': us.get('reason'),
                    'hk_direction': hk.get('direction'),
                    'hk_score': hk.get('score'),
                    'hk_reason': hk.get('reason'),
                    'a_direction': a.get('direction'),
                    'a_score': a.get('score'),
                    'a_reason': a.get('reason'),
                    'risk_events': result.get('risk_events'),
                    'status': '0',
                }
            )
        else:
            analysis_record.update({'status': '1', 'error_msg': (ai_result.get('error') or '')[:2000]})
        try:
            db_analysis = await SentimentAnalysisDao.add_analysis(query_db, analysis_record)
            # commit 后 ORM 会 expire，同步读属性会触发 MissingGreenlet；先取出主键
            analysis_id = db_analysis.analysis_id
            if ai_result['ok']:
                await SentimentNewsDao.mark_analyzed(query_db, news_ids)
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            raise e
        if ai_result['ok']:
            return {'analyzed': len(news_ids), 'analysisId': analysis_id, 'message': '分析成功'}
        return {
            'analyzed': 0,
            'analysisId': analysis_id,
            'message': f'分析失败: {ai_result["error"]}',
        }

    # ---------- 采集+分析组合（供定时任务调用） ----------

    @classmethod
    async def collect_and_analyze_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        """
        采集一次舆情，并根据配置决定是否自动执行AI分析service
        """
        collect_result = await cls.collect_news_services(query_db)
        result: dict[str, Any] = {**collect_result, 'analyzed': 0, 'analysisId': None}
        config = await cls.get_ai_config_services(query_db)
        if config.auto_analyze == '1' and collect_result['saved'] > 0:
            try:
                analyze_result = await cls.run_analysis_services(query_db)
                result.update(analyze_result)
            except ServiceException as e:
                logger.warning(f'[舆情任务] 自动分析跳过: {e.message}')
                result['message'] = e.message
        return result
