import asyncio
import json
import re
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from module_ai.dao.ai_model_dao import AiModelDao
from module_market.service.market_analyzer_service import MarketAiAnalyzer
from module_quant.service.factor_service import FactorService
from utils.crypto_util import CryptoUtil
from utils.influx_util import InfluxUtil
from utils.log_util import logger

ONE_SHOT_SYSTEM_PROMPT = """你是一名国际顶尖量化对冲基金的高级投资总监与量化架构师。
系统会给你某只股票的最新高阶量化因子（含趋势、价型、动量、突破、量能资金、回归、波动、流动性8大因子族及Alpha高阶特征）与近期K线快照。
请你基于严格的客观量化数据，进行 One-Shot 全景综合研判。

请严格按以下 JSON 格式输出，不要包含任何 markdown 代码块以外的解释或杂质：
{
  "score": 综合技术评分(0-100的数字),
  "decision": "STRONG_BUY|BUY|HOLD|SELL|STRONG_SELL",
  "confidence": 决策置信度(0-100数字),
  "risk_level": "low|medium|high",
  "trend_summary": "对当前量化形态与多空力量的精炼研判(100字以内)",
  "support_levels": [支撑位1, 支撑位2],
  "resistance_levels": [压力位1, 压力位2],
  "operation_advice": "针对该标的的明确交易与风控操作策略(100字以内)",
  "catalyst_analysis": "核心催化剂与风险触发条件(80字以内)"
}"""


class UnifiedAiService:
    """
    One-Shot 统一全景 AI 研判终端服务
    """

    @classmethod
    def _build_oneshot_prompt(cls, symbol: str, name: str, factor_data: dict[str, Any], klines: list[dict[str, Any]]) -> str:
        metrics = factor_data.get('metrics', {})
        score = factor_data.get('score', {})

        lines = [
            f"标的：{name} ({symbol})",
            f"最新收盘价: {metrics.get('latestClose')} | 当日涨跌幅: {metrics.get('dayChangePercent')}%",
            "",
            "【8大因子族计算特征快照】",
            f"- 趋势因子: MA20={metrics.get('ma20')}, MA60={metrics.get('ma60')}, ADX14={metrics.get('adx14')}, MACD_Hist={metrics.get('macdHist')}",
            f"- 价型因子: K线实体={metrics.get('kMid')}, 上影={metrics.get('upperShadow')}, 下影={metrics.get('lowerShadow')}, 布林%B={metrics.get('bollPercentB20')}",
            f"- 动量因子: RSI14={metrics.get('rsi14')}, ROC12={metrics.get('roc12')}%, KDJ_K={metrics.get('stochK14')}, CCI={metrics.get('cci20')}",
            f"- 突破因子: 距20日高点={metrics.get('distanceHigh20')}%, 距60日高点={metrics.get('distanceHigh60')}%",
            f"- 资金量能: 20日量比={metrics.get('volumeRatio20')}, OBV斜率={metrics.get('obvSlope20')}, MFI14={metrics.get('mfi14')}, CMF={metrics.get('cmf20')}",
            f"- 波动与回撤: 20日波动率={metrics.get('volatility20')}%, ATR%={metrics.get('atr14Percent')}%, 60日最大回撤={metrics.get('maxDrawdown60')}%",
            f"- 高阶Alpha因子: {json.dumps(metrics.get('alphaFactors', {}), ensure_ascii=False)}",
            f"- 系统预评分: {score.get('total')}分, 风险等级: {score.get('riskLevel')}, 标签: {','.join(score.get('tags', []))}",
            "",
            "近期日K线走势（最近10根）：",
        ]
        for k in klines[-10:]:
            lines.append(f"日期:{k.get('date')}, 收盘:{k.get('close')}, 涨跌%:{k.get('change_rate', 0)}, 成交量:{k.get('volume')}")

        lines.append("\n请严格按系统提示的 JSON 格式输出最终的 One-Shot 研判报告。")
        return "\n".join(lines)

    @classmethod
    async def analyze_symbol_oneshot(
        cls, db: AsyncSession, symbol: str, market: str = 'US'
    ) -> dict[str, Any]:
        """
        对单标的执行 One-Shot 全景 AI 研判
        """
        # 1. 解析 AI 模型配置
        ai_model = await AiModelDao.resolve_ai_model_for_business(db, 'sentiment')
        if not ai_model or not ai_model.base_url or not ai_model.api_key:
            return {
                'ok': False,
                'message': '未配置 AI 模型连接，请在 AI 模型管理中配置 API Key 与 Base URL',
            }

        api_key = CryptoUtil.decrypt(ai_model.api_key) if ai_model.api_key else ''
        base_url = ai_model.base_url.rstrip('/')
        if not base_url.endswith('/chat/completions'):
            url = f"{base_url}/chat/completions"
        else:
            url = base_url

        # 2. 拉取 K 线并计算多因子
        klines = await asyncio.to_thread(InfluxUtil.query_klines, market, symbol, '-1y', 'now()', 320)
        if not klines or len(klines) < 20:
            return {'ok': False, 'message': f'标的 {symbol} K线数据不足，请先执行行情同步'}

        factor_data = FactorService.compute_from_klines(klines, strategy_profile='balanced')
        user_prompt = cls._build_oneshot_prompt(symbol, symbol, factor_data, klines)

        payload = {
            'model': ai_model.model_code,
            'temperature': ai_model.temperature or 0.2,
            'messages': [
                {'role': 'system', 'content': ONE_SHOT_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt},
            ],
        }
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            raw_text = data['choices'][0]['message']['content'] or ''
        except Exception as exc:
            logger.error(f'[One-Shot AI] 调用大模型失败: {exc}')
            return {'ok': False, 'message': f'大模型调用失败: {exc}'}

        # 3. 解析 JSON
        try:
            parsed = MarketAiAnalyzer._parse_response(raw_text)
            return {
                'ok': True,
                'symbol': symbol,
                'market': market,
                'modelName': ai_model.model_code,
                'result': parsed,
                'factors': factor_data.get('metrics'),
                'score': factor_data.get('score'),
                'raw': raw_text,
            }
        except Exception as exc:
            logger.warning(f'[One-Shot AI] 解析 JSON 失败: {exc}')
            return {'ok': True, 'symbol': symbol, 'result': None, 'raw': raw_text, 'message': '模型已返回文本'}
