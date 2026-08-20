"""
量化策略服务：基于因子打分产出交易信号（BUY/HOLD/SELL）。
支持动态 Profile 阈值覆盖与异步并发批量扫描加速。
"""

from __future__ import annotations

import asyncio
from typing import Any

from module_quant.service.factor_service import FactorService
from utils.log_util import logger

# 默认策略档位 -> 决策阈值（BUY 置信度门槛、允许的最高风险）
PROFILE_THRESHOLDS: dict[str, dict[str, Any]] = {
    'conservative': {'buy': 72, 'sell': 42, 'max_risk': 'medium'},
    'balanced': {'buy': 64, 'sell': 38, 'max_risk': 'high'},
    'aggressive': {'buy': 56, 'sell': 32, 'max_risk': 'high'},
}

_RISK_RANK = {'low': 0, 'medium': 1, 'high': 2}


def decide_signal(
    score: dict[str, Any],
    strategy_profile: str = 'balanced',
    custom_thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    根据因子打分决定交易信号。支持动态自定义阈值注入。

    :param score: FactorService.score_metrics 的输出
    :param strategy_profile: 策略档位
    :param custom_thresholds: 动态自定义阈值配置 {'buy': int, 'sell': int, 'max_risk': str}
    :return: {'signal': BUY/HOLD/SELL, 'confidence': int, 'reason': str}
    """
    profile = strategy_profile if strategy_profile in PROFILE_THRESHOLDS else 'balanced'
    thresholds = dict(PROFILE_THRESHOLDS[profile])
    if custom_thresholds:
        if 'buy' in custom_thresholds or 'buyThreshold' in custom_thresholds:
            thresholds['buy'] = float(custom_thresholds.get('buy') or custom_thresholds.get('buyThreshold') or thresholds['buy'])
        if 'sell' in custom_thresholds or 'sellThreshold' in custom_thresholds:
            thresholds['sell'] = float(custom_thresholds.get('sell') or custom_thresholds.get('sellThreshold') or thresholds['sell'])
        if 'max_risk' in custom_thresholds:
            thresholds['max_risk'] = str(custom_thresholds['max_risk'])

    total = float(score.get('total') or 0.0)
    confidence = int(round(total))
    risk_level = str(score.get('riskLevel') or 'low').lower()
    trend_direction = str(score.get('trendDirection') or 'sideways').lower()
    tags = score.get('tags') or []

    max_risk_rank = _RISK_RANK.get(thresholds['max_risk'], 2)
    risk_rank = _RISK_RANK.get(risk_level, 0)

    # 卖出：趋势向下 或 得分过低 或 风险超限
    if trend_direction == 'down' or total <= thresholds['sell'] or risk_rank > max_risk_rank:
        reasons = []
        if trend_direction == 'down':
            reasons.append('趋势转弱')
        if total <= thresholds['sell']:
            reasons.append(f'综合分偏低({total})')
        if risk_rank > max_risk_rank:
            reasons.append(f'风险{risk_level}超出{profile}上限')
        return {'signal': 'SELL', 'confidence': confidence, 'reason': '；'.join(reasons) or '规避风险'}

    # 买入：达到门槛 且 风险可接受 且 趋势不向下
    if total >= thresholds['buy'] and risk_rank <= max_risk_rank and trend_direction != 'down':
        reason = f'综合分{total}达标；' + '、'.join(tags[:3])
        return {'signal': 'BUY', 'confidence': confidence, 'reason': reason}

    return {'signal': 'HOLD', 'confidence': confidence, 'reason': f'综合分{total}，等待更强信号'}


class StrategyService:
    """
    量化策略服务层（信号生成）。
    """

    @classmethod
    def evaluate_symbol(
        cls,
        symbol: str,
        market: str = 'US',
        strategy_profile: str = 'balanced',
        custom_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        对单个标的：拉K线 -> 算因子 -> 打分 -> 决策信号。

        :return: {symbol, market, signal, score, confidence, reason, factor_json(dict)} 或 {ok:False}
        """
        result = FactorService.compute_symbol(symbol, market, strategy_profile)
        if not result.get('ok'):
            logger.warning(f'[量化策略] {symbol}({market}) 因子计算跳过: {result.get("reason")}')
            return {
                'ok': False,
                'symbol': symbol,
                'market': market,
                'signal': 'HOLD',
                'score': 0.0,
                'confidence': 0,
                'reason': result.get('reason') or '数据不足',
                'factor_json': {},
            }
        score = result['score']
        metrics = result.get('metrics') or {}
        decision = decide_signal(score, strategy_profile, custom_thresholds=custom_config)
        return {
            'ok': True,
            'symbol': symbol,
            'market': market,
            'price': metrics.get('latestClose'),
            'signal': decision['signal'],
            'score': score['total'],
            'confidence': decision['confidence'],
            'reason': decision['reason'],
            'factor_json': {'score': score, 'metrics': metrics},
        }

    @classmethod
    async def run_strategy_cycle_async(
        cls,
        symbols: list[dict[str, str]] | list[str],
        profile: str = 'balanced',
        market: str = 'US',
        custom_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        异步高并发批量跑策略，利用 asyncio 并发计算因子与信号。
        """
        items: list[tuple[str, str]] = []
        for item in symbols or []:
            if isinstance(item, dict):
                sym = str(item.get('symbol') or '').strip()
                mkt = str(item.get('market') or market).strip().upper()
            else:
                sym = str(item or '').strip()
                mkt = market
            if sym:
                items.append((sym, mkt))

        if not items:
            return {'profile': profile, 'symbolsCount': 0, 'signalCount': 0, 'signals': []}

        # 异步并发执行
        tasks = [
            asyncio.to_thread(cls.evaluate_symbol, sym, mkt, profile, custom_config)
            for sym, mkt in items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        signals = [r for r in results if isinstance(r, dict)]

        # BUY/SELL 视为有效信号；按综合分降序
        actionable = [s for s in signals if s.get('signal') in ('BUY', 'SELL')]
        signals.sort(key=lambda s: s.get('score') or 0.0, reverse=True)
        return {
            'profile': profile,
            'symbolsCount': len(signals),
            'signalCount': len(actionable),
            'signals': signals,
        }

    @classmethod
    def run_strategy_cycle(
        cls,
        symbols: list[dict[str, str]] | list[str],
        profile: str = 'balanced',
        market: str = 'US',
        custom_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        同步兼容入口：如果在已有事件循环中调用，退化为快速单批次计算；否则启动异步执行。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 已在事件循环中（例如被同步上下文间接调用），使用本地多标的串行/列表推导保障安全
            signals = []
            for item in symbols or []:
                if isinstance(item, dict):
                    sym = str(item.get('symbol') or '').strip()
                    mkt = str(item.get('market') or market).strip().upper()
                else:
                    sym = str(item or '').strip()
                    mkt = market
                if sym:
                    signals.append(cls.evaluate_symbol(sym, mkt, profile, custom_config))
            actionable = [s for s in signals if s.get('signal') in ('BUY', 'SELL')]
            signals.sort(key=lambda s: s.get('score') or 0.0, reverse=True)
            return {
                'profile': profile,
                'symbolsCount': len(signals),
                'signalCount': len(actionable),
                'signals': signals,
            }
        else:
            return asyncio.run(cls.run_strategy_cycle_async(symbols, profile, market, custom_config))
