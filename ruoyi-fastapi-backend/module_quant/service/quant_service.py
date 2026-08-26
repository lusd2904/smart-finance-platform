"""
量化模块业务编排服务层：串联 DAO、因子/策略引擎、长桥接入。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from common.vo import CrudResponseModel, PageModel
from exceptions.exception import ServiceException
from module_quant.dao.quant_dao import (
    QuantLongbridgeConfigDao,
    QuantSnapshotDao,
    QuantStrategyDao,
    QuantWatchlistDao,
)
from module_quant.entity.vo.quant_vo import (
    AddQuantWatchlistModel,
    QuantLongbridgeConfigModel,
    QuantStrategyRunPageQueryModel,
    QuantWatchlistPageQueryModel,
    RunStrategyModel,
)
from module_quant.service.factor_service import FactorService
from module_quant.service.longbridge_service import LongbridgeService, resolve_longbridge_user_id
from module_quant.service.strategy_service import StrategyService
from utils.crypto_util import CryptoUtil
from utils.log_util import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

VALID_PROFILES = {'conservative', 'balanced', 'aggressive'}


def _factor_summary(factor_json: Any) -> dict[str, Any]:
    """信号表只留打分摘要；Alpha 明细走 quant_alpha101/158_value。"""
    if not isinstance(factor_json, dict):
        return {}
    metrics = factor_json.get('metrics') if isinstance(factor_json.get('metrics'), dict) else {}
    score = factor_json.get('score') if isinstance(factor_json.get('score'), dict) else {}
    return {
        'score': score,
        'latestClose': metrics.get('latestClose'),
        'tradeDate': metrics.get('tradeDate'),
        'alpha101Count': metrics.get('alpha101Count') or 0,
        'alpha158Count': metrics.get('alpha158Count') or 0,
    }


class QuantService:
    """量化模块服务层"""

    # ------------------------------------------------------------ 因子 ---

    @classmethod
    def get_factor_schema_services(cls) -> dict[str, Any]:
        """获取因子体系定义"""
        return FactorService.get_factor_schema()

    @classmethod
    async def load_profile_config(
        cls, query_db: AsyncSession, profile: str, user_id: int | None = None
    ) -> dict[str, Any]:
        """读取当前账户策略档位（有覆盖用覆盖，否则用系统默认）。"""
        try:
            from module_trade.service.platform_ext_service import PlatformExtService

            return await PlatformExtService.get_profile_config(query_db, profile, user_id=user_id)
        except Exception as exc:
            logger.warning(f'[量化] 读取策略配置失败 profile={profile} user={user_id}: {exc}')
        return {}

    @classmethod
    async def compute_factor_services(
        cls,
        symbol: str,
        market: str = 'US',
        profile: str = 'balanced',
        query_db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """计算某标的因子值+打分"""
        if not symbol:
            raise ServiceException(message='标的代码不能为空')
        safe_profile = profile if profile in VALID_PROFILES else 'balanced'
        weights = None
        if query_db is not None:
            weights = await cls.load_profile_config(query_db, safe_profile)
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            FactorService.compute_symbol,
            symbol.strip().upper(),
            (market or 'US').upper(),
            safe_profile,
            '-1y',
            weights,
        )
        if not result.get('ok'):
            return {
                'symbol': symbol,
                'market': market,
                'ok': False,
                'reason': result.get('reason') or '因子计算失败',
            }
        if query_db is not None:
            try:
                from module_quant.dao.quant_dao import QuantSnapshotDao

                snap = await QuantSnapshotDao.get_factor_snapshot(
                    query_db, symbol.strip().upper(), (market or 'US').upper()
                )
                if snap and snap.alpha_json:
                    payload = json.loads(snap.alpha_json or '{}') or {}
                    alpha_cs = payload.get('alphaCs') or {}
                    result['alphaCs'] = alpha_cs
                    result['alphaCsCount'] = len(alpha_cs)
                    metrics = result.get('metrics') or {}
                    metrics['alphaCs'] = alpha_cs
                    metrics['alphaCsCount'] = len(alpha_cs)
                    result['metrics'] = metrics
            except Exception as exc:
                logger.info(f'[因子] 截面 rank 附加跳过: {exc}')
        return result

    # ------------------------------------------------------------ 自选池 ---

    @classmethod
    async def get_watchlist_services(
        cls,
        query_db: AsyncSession,
        query_object: QuantWatchlistPageQueryModel,
        is_page: bool = True,
        user_id: int | None = None,
    ) -> PageModel | list[dict[str, Any]]:
        """获取自选池分页列表（user_id 非空时按账号隔离）"""
        return await QuantWatchlistDao.get_watchlist(query_db, query_object, is_page, user_id=user_id)

    @classmethod
    async def add_watchlist_services(
        cls, query_db: AsyncSession, add_model: AddQuantWatchlistModel, user_id: int | None = None
    ) -> CrudResponseModel:
        """新增自选标的（账号内去重）"""
        symbol = (add_model.symbol or '').strip().upper()
        market = (add_model.market or 'US').strip().upper()
        if not symbol:
            raise ServiceException(message='标的代码不能为空')
        if not user_id:
            raise ServiceException(message='无法识别当前用户')
        existing = await QuantWatchlistDao.get_by_symbol(query_db, symbol, market, user_id=user_id)
        if existing:
            raise ServiceException(message=f'{symbol}({market}) 已在自选池中')
        try:
            await QuantWatchlistDao.add_watchlist(
                query_db,
                {
                    'user_id': user_id,
                    'symbol': symbol,
                    'market': market,
                    'note': add_model.note,
                    'enabled': '1',
                    'create_time': datetime.now(),
                },
            )
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def delete_watchlist_services(
        cls, query_db: AsyncSession, ids: str, user_id: int | None = None
    ) -> CrudResponseModel:
        """删除自选标的（user_id 非空时只能删自己的）"""
        if not ids:
            raise ServiceException(message='传入ID为空')
        try:
            id_list = [int(i) for i in ids.split(',') if i.strip()]
        except ValueError:
            raise ServiceException(message='ID格式非法，应为逗号分隔的数字') from None
        try:
            await QuantWatchlistDao.delete_watchlist(query_db, id_list, user_id=user_id)
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    # ------------------------------------------------------------ 策略 ---

    @classmethod
    async def run_strategy_services(
        cls, query_db: AsyncSession, run_model: RunStrategyModel, user_id: int | None = None
    ) -> dict[str, Any]:
        """
        跑一次策略并入库。symbols 不传则用当前用户自选池（未识别用户时退回全池）。
        """
        profile = run_model.profile if run_model.profile in VALID_PROFILES else 'balanced'
        profile_cfg = await cls.load_profile_config(query_db, profile, user_id=user_id)

        # 确定标的列表
        if run_model.symbols:
            targets = [{'symbol': s.strip().upper(), 'market': 'US'} for s in run_model.symbols if s and s.strip()]
        else:
            watchlist = await QuantWatchlistDao.get_enabled_symbols(query_db, user_id=user_id)
            targets = [{'symbol': w.symbol, 'market': w.market} for w in watchlist]
            # 自选池为空则退回精选池（前端提示“留空则全市场”）
            if not targets:
                from module_market.constant.instruments import TARGET_INSTRUMENTS
                targets = [{'symbol': it[0], 'market': it[2]} for it in TARGET_INSTRUMENTS]

        if not targets:
            return {'runId': None, 'symbolsCount': 0, 'signalCount': 0, 'signals': [],
                    'message': '无可用标的'}

        cycle_id = uuid.uuid4().hex
        # 策略周期含逐标的Influx查询与指标计算，放线程池执行避免阻塞事件循环
        cycle_result = await asyncio.get_running_loop().run_in_executor(
            None, StrategyService.run_strategy_cycle, targets, profile, 'US', profile_cfg
        )

        # 落库
        try:
            run = await QuantStrategyDao.add_run(
                query_db,
                {
                    'cycle_id': cycle_id,
                    'user_id': user_id or 1,
                    'strategy_profile': profile,
                    'symbols_count': cycle_result['symbolsCount'],
                    'signal_count': cycle_result['signalCount'],
                    'create_time': datetime.now(),
                },
            )
            run_id = run.run_id  # commit 后 ORM 属性会过期，提前取出主键
            signal_rows = [
                {
                    'run_id': run_id,
                    'user_id': user_id or 1,
                    'symbol': s['symbol'],
                    'signal': s['signal'],
                    'score': s.get('score'),
                    'confidence': s.get('confidence'),
                    'reason': (s.get('reason') or '')[:500],
                    'factor_json': json.dumps(_factor_summary(s.get('factor_json')), ensure_ascii=False),
                    'create_time': datetime.now(),
                }
                for s in cycle_result['signals']
            ]
            if signal_rows:
                await QuantStrategyDao.add_signals(query_db, signal_rows)
            for s in cycle_result['signals']:
                fj = s.get('factor_json') or {}
                metrics = fj.get('metrics') if isinstance(fj, dict) else {}
                if not isinstance(metrics, dict):
                    continue
                await QuantSnapshotDao.replace_alpha_values(
                    query_db,
                    symbol=s.get('symbol') or '',
                    market=s.get('market') or 'US',
                    as_of=str(metrics.get('tradeDate') or '')[:16],
                    alpha101=metrics.get('alpha101') or {},
                    alpha158=metrics.get('alpha158') or {},
                )
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            raise e

        logger.info(
            f'[量化策略] profile={profile} 标的={cycle_result["symbolsCount"]} '
            f'信号={cycle_result["signalCount"]} runId={run_id}'
        )
        return {
            'runId': run_id,
            'cycleId': cycle_id,
            'profile': profile,
            'symbolsCount': cycle_result['symbolsCount'],
            'signalCount': cycle_result['signalCount'],
            'signals': [
                {
                    'symbol': s['symbol'],
                    'market': s.get('market'),
                    'signal': s['signal'],
                    'score': s.get('score'),
                    'confidence': s.get('confidence'),
                    'reason': s.get('reason'),
                }
                for s in cycle_result['signals']
            ],
            'message': '策略执行完成',
        }

    @classmethod
    async def get_strategy_history_services(
        cls, query_db: AsyncSession, query_object: QuantStrategyRunPageQueryModel, is_page: bool = True
    ) -> PageModel | list[dict[str, Any]]:
        """获取策略运行历史分页列表"""
        return await QuantStrategyDao.get_run_list(query_db, query_object, is_page)

    # ------------------------------------------------------------ 扫描运行台账 ---

    @classmethod
    async def get_scan_runs_services(cls, query_db: AsyncSession, limit: int = 20) -> dict[str, Any]:
        """只读扫描运行列表（最近 N 条）"""
        runs = await QuantStrategyDao.get_scan_runs(query_db, limit=limit)
        signals_by_run = await QuantStrategyDao.get_signals_by_runs(query_db, [r.run_id for r in runs])
        items = []
        opportunity_total = 0
        for run in runs:
            signals = signals_by_run.get(run.run_id, [])
            opportunities = [s for s in signals if s.signal == 'BUY']
            skipped = [s for s in signals if s.signal == 'HOLD']
            opportunity_total += len(opportunities)
            items.append(
                {
                    'runId': run.run_id,
                    'cycleId': run.cycle_id,
                    'status': 'completed',
                    'reason': 'executed' if opportunities else 'no_opportunity',
                    'message': f'评估{run.symbols_count}个标的，产出{run.signal_count}个可执行信号',
                    'strategyProfile': run.strategy_profile,
                    'targetCount': run.symbols_count,
                    'evaluatedCount': run.symbols_count,
                    'opportunityCount': len(opportunities),
                    'submittedCount': 0,
                    'skippedCount': len(skipped),
                    'signalCount': run.signal_count,
                    'startedAt': run.create_time.strftime('%Y-%m-%d %H:%M:%S') if run.create_time else None,
                    'finishedAt': run.create_time.strftime('%Y-%m-%d %H:%M:%S') if run.create_time else None,
                    'source': 'manual_or_scheduler',
                }
            )
        return {
            'items': items,
            'summary': {
                'recordCount': len(items),
                'completedCount': len(items),
                'opportunityCount': opportunity_total,
                'submittedCount': 0,
            },
            'limit': limit,
        }

    @classmethod
    async def get_scan_run_detail_services(
        cls, query_db: AsyncSession, cycle_or_run_id: str
    ) -> dict[str, Any]:
        """扫描运行详情（含候选/机会/跳过）"""
        run = None
        if str(cycle_or_run_id).isdigit():
            run = await QuantStrategyDao.get_run_by_id(query_db, int(cycle_or_run_id))
        if not run:
            run = await QuantStrategyDao.get_run_by_cycle_id(query_db, str(cycle_or_run_id))
        if not run:
            raise ServiceException(message='扫描记录不存在')

        signals = await QuantStrategyDao.get_signals_by_run(query_db, run.run_id)
        opportunities = []
        candidates = []
        skipped = []
        for s in signals:
            factor = {}
            try:
                factor = json.loads(s.factor_json) if s.factor_json else {}
            except Exception:
                factor = {}
            score = factor.get('score') or {}
            row = {
                'symbol': s.symbol,
                'side': s.signal,
                'isOpportunity': s.signal == 'BUY',
                'confidence': s.confidence,
                'score': s.score,
                'riskLevel': score.get('riskLevel'),
                'reason': s.reason,
                'price': (factor.get('metrics') or {}).get('close') or (factor.get('metrics') or {}).get('price'),
            }
            candidates.append(row)
            if s.signal == 'BUY':
                opportunities.append(row)
            elif s.signal == 'HOLD':
                skipped.append({**row, 'skipReason': s.reason or '未达买入阈值'})
            else:
                skipped.append({**row, 'skipReason': s.reason or '卖出/规避'})

        return {
            'runId': run.run_id,
            'cycleId': run.cycle_id,
            'status': 'completed',
            'reason': 'executed' if opportunities else 'no_opportunity',
            'message': f'评估{run.symbols_count}个标的，机会{len(opportunities)}个',
            'strategyProfile': run.strategy_profile,
            'targetCount': run.symbols_count,
            'evaluatedCount': run.symbols_count,
            'opportunityCount': len(opportunities),
            'submittedCount': 0,
            'skippedCount': len(skipped),
            'startedAt': run.create_time.strftime('%Y-%m-%d %H:%M:%S') if run.create_time else None,
            'finishedAt': run.create_time.strftime('%Y-%m-%d %H:%M:%S') if run.create_time else None,
            'settings': {
                'profile': run.strategy_profile,
                'maxBuy': None,
                'minConfidence': None,
            },
            'positionControl': {
                'targetPositionPct': None,
                'dailyOrderLimit': None,
                'dailyAmountLimit': None,
            },
            'opportunities': opportunities,
            'candidates': candidates[:12],
            'skipped': skipped,
            'items': candidates,
        }

    @classmethod
    async def get_symbol_latest_scan_services(
        cls, query_db: AsyncSession, symbol: str, market: str = 'US', user_id: int | None = None
    ) -> dict[str, Any]:
        """单标的：最近趋势扫描 + 最近 AI 研判（趋势信号按账号隔离）"""
        from module_market.service.market_service import MarketService

        symbol = (symbol or '').strip().upper()
        market = (market or 'US').strip().upper()
        signal = await QuantStrategyDao.get_latest_signal_for_symbol(query_db, symbol, user_id=user_id)
        latest_trend = MarketService._map_signal_to_trend(signal)
        latest_ai = await MarketService.get_latest_ai_analysis(query_db, symbol, market)
        return {
            'symbol': symbol,
            'market': market,
            'latestTrendScan': latest_trend,
            'latestAiAnalysis': latest_ai,
        }

    # ------------------------------------------------------------ 长桥 ---

    @classmethod
    async def _sync_longbridge_credentials(cls, query_db: AsyncSession, user_id: int | None = None) -> None:
        """从DB读取当前用户长桥凭据注入到 LongbridgeService（DB优先于env）。"""
        await LongbridgeService.ensure_credentials_from_db(query_db, user_id)

    @classmethod
    async def test_longbridge_services(cls, query_db: AsyncSession, user_id: int | None = None) -> dict[str, Any]:
        """长桥连通性测试，只使用当前用户自己的凭据行。"""
        target_id = resolve_longbridge_user_id(user_id)
        config = await QuantLongbridgeConfigDao.get_config(query_db, target_id)
        if not config or not (config.app_key or config.app_secret or config.access_token):
            return {'configured': False, 'connected': False, 'message': '长桥凭据未配置'}
        await cls._sync_longbridge_credentials(query_db, target_id)
        return LongbridgeService.test_connection()

    @classmethod
    async def get_longbridge_config_services(
        cls, query_db: AsyncSession, user_id: int | None = None
    ) -> QuantLongbridgeConfigModel:
        """
        获取当前用户长桥凭据配置（app_secret/access_token 脱敏）。
        无本行时返回空配置，不读取其他用户或 env 以免串号。
        """
        target_id = resolve_longbridge_user_id(user_id)
        config = await QuantLongbridgeConfigDao.get_config(query_db, target_id)
        if config:
            return QuantLongbridgeConfigModel(
                id=config.id,
                userId=getattr(config, 'user_id', None) or target_id,
                appKey=config.app_key or '',
                appSecret=cls._mask(cls._decrypt_or_raw(config.app_secret)),
                accessToken=cls._mask(cls._decrypt_or_raw(config.access_token)),
                region=config.region or 'cn',
                autoTradeEnabled=str(getattr(config, 'auto_trade_enabled', '0') or '0') == '1',
                dailyBuyRatio=float(getattr(config, 'daily_buy_ratio', None) or 0.20),
                maxSymbolPositionPct=float(getattr(config, 'max_symbol_position_pct', None) or 0.10),
                updateTime=config.update_time,
            )
        return QuantLongbridgeConfigModel(
            userId=target_id,
            appKey='',
            appSecret='',
            accessToken='',
            region='cn',
            autoTradeEnabled=False,
            dailyBuyRatio=0.20,
            maxSymbolPositionPct=0.10,
        )

    @classmethod
    async def save_longbridge_config_services(
        cls, query_db: AsyncSession, config: QuantLongbridgeConfigModel, user_id: int | None = None
    ) -> CrudResponseModel:
        """保存当前用户长桥凭据；忽略请求体中的 user_id，以登录用户为准。"""
        target_id = resolve_longbridge_user_id(user_id)
        existing = await QuantLongbridgeConfigDao.get_config(query_db, target_id)
        app_secret = config.app_secret
        access_token = config.access_token
        if cls._is_masked(app_secret):
            app_secret = existing.app_secret if existing else ''
        else:
            app_secret = CryptoUtil.encrypt(app_secret) if app_secret else ''
        if cls._is_masked(access_token):
            access_token = existing.access_token if existing else ''
        else:
            access_token = CryptoUtil.encrypt(access_token) if access_token else ''
        config_dict = {
            'user_id': target_id,
            'app_key': config.app_key,
            'app_secret': app_secret,
            'access_token': access_token,
            'region': (config.region or 'cn').strip().lower(),
            'update_time': datetime.now(),
        }
        try:
            await QuantLongbridgeConfigDao.save_config(query_db, config_dict, target_id)
            await query_db.commit()
            await cls._sync_longbridge_credentials(query_db, target_id)
            return CrudResponseModel(is_success=True, message='保存成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @staticmethod
    def _mask(value: str | None) -> str:
        """敏感值脱敏：仅保留末4位。"""
        if not value:
            return ''
        text = str(value)
        return f'****{text[-4:]}' if len(text) > 4 else '****'

    @staticmethod
    def _is_masked(value: str | None) -> bool:
        """判断是否为前端回显的脱敏占位值。"""
        return bool(value) and str(value).startswith('****')

    @staticmethod
    def _decrypt_or_raw(value: str | None) -> str:
        """解密凭据；兼容历史明文存量（解密失败按原值返回）。"""
        if not value:
            return ''
        try:
            return CryptoUtil.decrypt(value)
        except Exception:
            return value
