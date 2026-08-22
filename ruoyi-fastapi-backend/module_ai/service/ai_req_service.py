"""需求沟通群聊 + 需求清单。群成员不含 admin / niangao，固定一位 Grok。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.exception import ServiceException
from module_ai.dao.ai_model_dao import AiModelDao
from module_ai.dao.ai_req_dao import EXCLUDED_USERNAMES, AiReqDao
from module_ai.entity.do.ai_model_do import AiModels
from utils.crypto_util import CryptoUtil
from utils.log_util import logger

AI_USER = {'userId': 0, 'userName': 'grok', 'nickName': 'Grok', 'role': 'ai'}
STATUS_LABELS = {
    'pending': '待开发',
    'developing': '开发中',
    'testing': '测试中',
    'done': '已完成',
    'cancelled': '已取消',
}
VALID_STATUS = set(STATUS_LABELS)
VALID_PRIORITY = {'P0', 'P1', 'P2', 'P3'}

SYSTEM_PROMPT = """你是需求沟通群里的固定成员 Grok（xAI）。团队在讨论产品需求是否可行。
规则：
1. 用中文简短回复，先判断可行性、风险和范围，不要写代码。
2. 当讨论已经形成可执行优化点，或用户明确说「确定需求 / 写入清单 / 总结需求」时，在回复末尾附加且仅附加一段 JSON（不要用 markdown 代码块）：
{"action":"upsert_requirements","items":[{"title":"不超过40字","detail":"实现要点","priority":"P0|P1|P2|P3"}]}
3. 未确认时不要输出 action JSON。
4. 不要泄露密钥或编造已上线功能。"""


def _dump(payload: Any, limit: int = 20000) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)[:limit]


def extract_requirement_payload(text: str) -> list[dict[str, str]]:
    """从模型回复中提取 upsert_requirements 条目。"""
    raw = (text or '').strip()
    match = re.search(r'\{[\s\S]*"action"\s*:\s*"upsert_requirements"[\s\S]*\}', raw)
    if not match:
        return []
    blob = match.group(0)
    start, end = blob.find('{'), blob.rfind('}')
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(blob[start : end + 1])
    except Exception:
        return []
    items = data.get('items') if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        title = str(item.get('title') or '').strip()[:200]
        if not title:
            continue
        priority = str(item.get('priority') or 'P2').upper()
        if priority not in VALID_PRIORITY:
            priority = 'P2'
        out.append({'title': title, 'detail': str(item.get('detail') or '').strip()[:4000], 'priority': priority})
    return out


def public_item(row: Any) -> dict[str, Any]:
    return {
        'id': row.item_id,
        'title': row.title,
        'detail': row.detail,
        'priority': row.priority or 'P2',
        'status': row.status,
        'statusLabel': STATUS_LABELS.get(row.status or '', row.status),
        'createdBy': row.created_by_name,
        'remark': row.remark,
        'createTime': row.create_time.strftime('%Y-%m-%d %H:%M:%S') if row.create_time else None,
        'updateTime': row.update_time.strftime('%Y-%m-%d %H:%M:%S') if row.update_time else None,
    }


class AiReqService:
    @classmethod
    def is_member(cls, user_name: str | None) -> bool:
        return (user_name or '').lower() not in EXCLUDED_USERNAMES

    @classmethod
    def serialize_message(cls, row: Any) -> dict[str, Any]:
        return {
            'msgId': row.msg_id,
            'userId': row.user_id,
            'userName': row.user_name,
            'nickName': row.nick_name or row.user_name,
            'role': row.role,
            'content': row.content,
            'createTime': row.create_time.strftime('%Y-%m-%d %H:%M:%S') if row.create_time else None,
        }

    @classmethod
    async def room_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        users = await AiReqDao.list_members(query_db)
        members = [
            {
                'userId': u.user_id,
                'userName': u.user_name,
                'nickName': u.nick_name or u.user_name,
                'role': 'user',
            }
            for u in users
        ]
        members.append(dict(AI_USER))
        return {
            'roomId': 1,
            'title': '需求沟通',
            'excluded': sorted(EXCLUDED_USERNAMES),
            'members': members,
            'ai': dict(AI_USER),
        }

    @classmethod
    async def history_services(cls, query_db: AsyncSession, after_id: int = 0, limit: int = 200) -> dict[str, Any]:
        rows = await AiReqDao.list_messages(query_db, after_id=after_id, limit=limit)
        return {'items': [cls.serialize_message(r) for r in rows], 'count': len(rows)}

    @classmethod
    async def _resolve_grok(cls, query_db: AsyncSession) -> dict[str, Any]:
        models: list[AiModels] = []
        seen: set[int] = set()
        preferred = await AiModelDao.resolve_ai_model_for_business(query_db, 'chat')
        if preferred:
            models.append(preferred)
            seen.add(preferred.model_id)
        extras = (await query_db.execute(select(AiModels).where(AiModels.status == '0'))).scalars().all()
        for model in extras:
            if model.model_id not in seen:
                seen.add(model.model_id)
                models.append(model)

        def score(model: AiModels) -> int:
            blob = f'{model.provider or ""} {model.model_code or ""} {model.model_name or ""}'.lower()
            n = 0
            if 'grok' in blob or 'xai' in blob:
                n += 10
            if (model.scope or '') == 'chat':
                n += 2
            if model.base_url and model.api_key and model.model_code:
                n += 1
            return n

        models.sort(key=score, reverse=True)
        picked = next((m for m in models if m.base_url and m.api_key and m.model_code), None)
        if not picked:
            return {'available': False}
        try:
            api_key = CryptoUtil.decrypt(picked.api_key) if picked.api_key else None
        except Exception:
            api_key = picked.api_key
        return {
            'available': bool(picked.base_url and api_key and picked.model_code),
            'baseUrl': picked.base_url,
            'apiKey': api_key,
            'modelName': picked.model_code,
            'provider': picked.provider,
        }

    @classmethod
    async def _call_grok(cls, conf: dict[str, Any], history: list[dict[str, str]], user_text: str) -> str:
        url = str(conf['baseUrl']).rstrip('/')
        if not url.endswith('/chat/completions'):
            url = f'{url}/chat/completions'
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        for item in history[-16:]:
            role = 'assistant' if item.get('role') == 'ai' else 'user'
            messages.append({'role': role, 'content': item.get('content') or ''})
        messages.append({'role': 'user', 'content': user_text})
        payload = {'model': conf['modelName'], 'temperature': 0.3, 'messages': messages}
        headers = {'Authorization': f'Bearer {conf["apiKey"]}', 'Content-Type': 'application/json'}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return (data.get('choices') or [{}])[0].get('message', {}).get('content') or ''

    @classmethod
    async def _write_items(
        cls,
        query_db: AsyncSession,
        items: list[dict[str, str]],
        created_by: int | None,
        created_by_name: str | None,
        source_msg_id: int | None,
    ) -> list[dict[str, Any]]:
        saved = []
        for item in items:
            row = await AiReqDao.add_item(
                query_db,
                {
                    'title': item['title'],
                    'detail': item.get('detail'),
                    'priority': item.get('priority') or 'P2',
                    'status': 'pending',
                    'source_msg_id': source_msg_id,
                    'created_by': created_by,
                    'created_by_name': created_by_name,
                    'create_time': datetime.now(),
                    'update_time': datetime.now(),
                },
            )
            saved.append(public_item(row))
        return saved

    @classmethod
    async def _enqueue(cls, job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        from utils.job_queue import JobQueue

        ticket = await JobQueue.submit(job_type, payload)
        if not ticket:
            raise ServiceException(message='后台任务队列暂不可用，请稍后重试')
        return ticket

    @classmethod
    async def _add_user_message(
        cls,
        query_db: AsyncSession,
        user_id: int,
        user_name: str,
        nick_name: str | None,
        content: str,
    ) -> dict[str, Any]:
        row = await AiReqDao.add_message(
            query_db,
            {
                'room_id': 1,
                'user_id': user_id,
                'user_name': user_name,
                'nick_name': nick_name or user_name,
                'role': 'user',
                'content': content,
                'create_time': datetime.now(),
            },
        )
        msg = cls.serialize_message(row)
        await query_db.commit()
        return msg

    @classmethod
    async def _append_ai_reply(
        cls,
        query_db: AsyncSession,
        reply: str,
        created_by: int | None,
        created_by_name: str | None,
        write_items: bool,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        ai_row = await AiReqDao.add_message(
            query_db,
            {
                'room_id': 1,
                'user_id': 0,
                'user_name': 'grok',
                'nick_name': 'Grok',
                'role': 'ai',
                'content': reply,
                'create_time': datetime.now(),
            },
        )
        ai_msg = cls.serialize_message(ai_row)
        written: list[dict[str, Any]] = []
        parsed = extract_requirement_payload(reply) if write_items else []
        if parsed:
            written = await cls._write_items(
                query_db,
                parsed,
                created_by=created_by,
                created_by_name=created_by_name,
                source_msg_id=int(ai_msg.get('msgId') or 0) or None,
            )
        await query_db.commit()
        return ai_msg, written

    @classmethod
    async def enqueue_send_services(
        cls,
        query_db: AsyncSession,
        content: str,
        user_id: int,
        user_name: str,
        nick_name: str | None,
    ) -> dict[str, Any]:
        text = (content or '').strip()
        if not text:
            raise ServiceException(message='消息不能为空')
        if not cls.is_member(user_name):
            raise ServiceException(message='admin / niangao 不在需求沟通群中')
        user_msg = await cls._add_user_message(query_db, user_id, user_name, nick_name, text)
        ticket = await cls._enqueue(
            'req_send',
            {
                'userId': user_id,
                'userName': user_name,
                'nickName': nick_name or user_name,
                'userMsgId': user_msg.get('msgId'),
            },
        )
        return {**ticket, 'userMessage': user_msg}

    @classmethod
    async def process_send_job(cls, query_db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = int(payload.get('userId') or 0)
        user_name = str(payload.get('userName') or '')
        nick_name = str(payload.get('nickName') or user_name)
        user_msg_id = int(payload.get('userMsgId') or 0)
        user_row = await AiReqDao.get_message(query_db, user_msg_id) if user_msg_id else None
        if not user_row:
            raise ServiceException(message=f'需求沟通消息不存在: {user_msg_id}')
        text = user_row.content or ''
        history_rows = await AiReqDao.list_messages(query_db, after_id=0, limit=24)
        history = [{'role': r.role, 'content': r.content} for r in history_rows if r.msg_id != user_msg_id]
        conf = await cls._resolve_grok(query_db)
        if conf.get('available'):
            try:
                reply = await cls._call_grok(conf, history, f'{nick_name or user_name}: {text}')
            except Exception as exc:
                logger.warning(f'[需求沟通] Grok 调用失败: {exc}')
                reply = f'Grok 暂时不可用：{exc}。请稍后重试，或检查 AI 模型管理中的 chat/Grok 配置。'
        else:
            reply = '尚未配置可用的 Grok / chat 模型。请在「AI 模型管理」填写 Base URL、API Key 与模型编码后再讨论。'
        ai_msg, written = await cls._append_ai_reply(
            query_db, reply, created_by=user_id, created_by_name=nick_name or user_name, write_items=True
        )
        return {
            'aiMessage': ai_msg,
            'requirements': written,
            'count': len(written),
        }

    @classmethod
    async def enqueue_summarize_services(
        cls, query_db: AsyncSession, user_id: int, user_name: str, nick_name: str | None
    ) -> dict[str, Any]:
        if not cls.is_member(user_name):
            raise ServiceException(message='admin / niangao 不在需求沟通群中')
        rows = await AiReqDao.list_messages(query_db, after_id=0, limit=40)
        if len(rows) < 2:
            raise ServiceException(message='对话太少，请先讨论需求再总结')
        user_msg = await cls._add_user_message(
            query_db, user_id, user_name, nick_name, '请总结已确定的需求并写入需求清单。'
        )
        ticket = await cls._enqueue(
            'req_summarize',
            {
                'userId': user_id,
                'userName': user_name,
                'nickName': nick_name or user_name,
                'userMsgId': user_msg.get('msgId'),
            },
        )
        return {
            **ticket,
            'userMessage': user_msg,
            'message': '已加入后台队列，Grok 总结完成后会写入清单',
        }

    @classmethod
    async def process_summarize_job(cls, query_db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = int(payload.get('userId') or 0)
        user_name = str(payload.get('userName') or '')
        nick_name = str(payload.get('nickName') or user_name)
        user_msg_id = int(payload.get('userMsgId') or 0)
        rows = await AiReqDao.list_messages(query_db, after_id=0, limit=40)
        history = [{'role': r.role, 'content': r.content} for r in rows if r.msg_id != user_msg_id]
        prompt = (
            '请根据以上群聊，把已经达成一致的需求总结成优化点并写入清单。'
            '必须输出 action=upsert_requirements 的 JSON。未达成一致的不要写入。'
        )
        conf = await cls._resolve_grok(query_db)
        if not conf.get('available'):
            reply = '尚未配置可用的 Grok / chat 模型，无法总结。请在「AI 模型管理」填写配置后再试。'
        else:
            try:
                reply = await cls._call_grok(conf, history, prompt)
            except Exception as exc:
                logger.warning(f'[需求沟通] 总结失败: {exc}')
                reply = f'Grok 调用失败：{exc}。请稍后重试。'
        ai_msg, written = await cls._append_ai_reply(
            query_db, reply, created_by=user_id, created_by_name=nick_name or user_name, write_items=True
        )
        return {
            'aiMessage': ai_msg,
            'requirements': written,
            'count': len(written),
            'message': f'已写入 {len(written)} 条需求' if written else '未解析到可写入的确定需求',
        }

    @classmethod
    async def list_items_services(cls, query_db: AsyncSession, status: str | None = None) -> dict[str, Any]:
        rows = await AiReqDao.list_items(query_db, status=status)
        return {'items': [public_item(r) for r in rows], 'count': len(rows)}

    @classmethod
    async def update_status_services(
        cls, query_db: AsyncSession, item_id: int, status: str, remark: str | None = None
    ) -> dict[str, Any]:
        if status not in VALID_STATUS:
            raise ServiceException(message='无效状态')
        row = await AiReqDao.get_item(query_db, item_id)
        if not row:
            raise ServiceException(message='需求不存在')
        values: dict[str, Any] = {'status': status}
        if remark is not None:
            values['remark'] = remark[:500]
        await AiReqDao.update_item(query_db, item_id, values)
        await query_db.commit()
        row = await AiReqDao.get_item(query_db, item_id)
        return public_item(row)

    @classmethod
    async def export_services(cls, query_db: AsyncSession, status: str | None = None) -> dict[str, Any]:
        rows = await AiReqDao.list_items(query_db, status=status, limit=500)
        items = [public_item(r) for r in rows]
        return {
            'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'filter': status or 'all',
            'count': len(items),
            'items': items,
        }
