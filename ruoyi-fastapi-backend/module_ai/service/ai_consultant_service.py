from __future__ import annotations

import asyncio
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from module_ai.dao.ai_model_dao import AiModelDao
from module_quant.service.longbridge_service import LongbridgeService
from utils.crypto_util import CryptoUtil
from utils.log_util import logger


class AiConsultantService:
    """
    持仓投研智能顾问：基于长桥账户/持仓上下文做多轮问答。
    """

    @classmethod
    async def chat_consultant(
        cls, db: AsyncSession, message: str, history: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        if not str(message or '').strip():
            return {'ok': False, 'message': '请输入要咨询的问题'}

        ai_model = await AiModelDao.resolve_ai_model_for_business(db, 'chat')
        if not ai_model or not ai_model.base_url or not ai_model.api_key:
            return {'ok': False, 'message': '未配置大模型连接，请先在 AI 模型管理中配置'}

        api_key = CryptoUtil.decrypt(ai_model.api_key) if ai_model.api_key else ''
        base_url = ai_model.base_url.rstrip('/')
        url = f'{base_url}/chat/completions' if not base_url.endswith('/chat/completions') else base_url

        await LongbridgeService.ensure_credentials_from_db(db)
        acc_raw, pos_res = await asyncio.gather(
            LongbridgeService.get_account_balance_async(),
            LongbridgeService.get_positions_async(),
        )
        acc = LongbridgeService.flatten_account(acc_raw)
        positions = pos_res.get('positions') or []

        pos_summary = []
        for p in positions:
            qty = p.get('quantity')
            available = p.get('availableQuantity')
            cost = p.get('costPrice')
            pos_summary.append(
                f"- {p.get('symbol')}: 持仓 {qty} 股, 可用 {available}, 成本价 {cost} {p.get('currency') or ''}"
            )
        pos_text = '\n'.join(pos_summary) if pos_summary else '（当前暂无持仓）'

        system_prompt = f"""你是一名资深的全球宏观与美股量化投资顾问。
你的服务对象当前在长桥证券持有以下资产组合：
- 总资产净值: ${acc.get('netAssets') or 0}
- 可用现金: ${acc.get('availableCash') or 0}
- 持仓标的明细：
{pos_text}

请你根据用户的提问，结合其真实持仓结构与市场宏观风控，给出理性、专业、严谨且可操作的投研建议。
注意：始终提示投资有风险，决策需谨慎。回答条理清晰，多采用要点与数据支撑。"""

        messages = [{'role': 'system', 'content': system_prompt}]
        if history:
            for h in history[-6:]:
                messages.append({'role': h.get('role', 'user'), 'content': h.get('content', '')})
        messages.append({'role': 'user', 'content': message})

        payload = {
            'model': ai_model.model_code,
            'temperature': ai_model.temperature or 0.5,
            'messages': messages,
        }
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            reply = data['choices'][0]['message']['content'] or ''
            return {
                'ok': True,
                'reply': reply,
                'modelName': ai_model.model_code,
                'portfolioContext': {
                    'positionsCount': len(positions),
                    'totalNetAssets': acc.get('netAssets'),
                    'availableCash': acc.get('availableCash'),
                },
            }
        except Exception as exc:
            logger.error(f'[投研顾问] 调用失败: {exc}')
            return {'ok': False, 'message': f'顾问咨询异常: {exc}'}
