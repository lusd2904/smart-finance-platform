"""需求沟通群聊 + 需求清单。群成员不含 admin / niangao；机器人由 AI 管理配置。"""

from __future__ import annotations

import asyncio
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

DEFAULT_AI_USER = {'userId': 0, 'userName': 'grok', 'nickName': 'Grok', 'role': 'ai', 'isDecider': True}
STATUS_LABELS = {
    'pending': '待开发',
    'developing': '开发中',
    'testing': '测试中',
    'done': '已完成',
    'cancelled': '已取消',
}
VALID_STATUS = set(STATUS_LABELS)
VALID_PRIORITY = {'P0', 'P1', 'P2', 'P3'}
CONFIRM_RE = re.compile(r'(确定需求|确认需求|写入清单|总结并写入|请总结|确认落地)')
CONFIRM_EXACT = {'确定', '确认', '同意', '就这样'}
MAX_ROUNDS = 3


def system_prompt(*, name: str, is_decider: bool, round_no: int, peer_notes: str, write_allowed: bool) -> str:
    role = f'你是需求沟通群里的 AI 成员「{name}」。只讨论需求沟通，不写代码。'
    round_rule = (
        '本轮是第 1 轮：独立判断可行性、风险、范围，不要提及其他 AI 当轮发言。'
        if round_no <= 1
        else f'本轮是第 {round_no} 轮：必须点评其他 AI 的观点并回应分歧。其他成员上一轮摘要：\n{peer_notes or "（暂无）"}'
    )
    if is_decider and write_allowed:
        write_rule = (
            '你是唯一清单确定者。用户已确认后，在回复末尾附加且仅附加一段 JSON（不要用 markdown 代码块）：'
            '{"action":"upsert_requirements","items":[{"title":"不超过40字","detail":"实现要点","priority":"P0|P1|P2|P3"}]}'
            '合并去重，未达成一致的不要写入。'
        )
    elif is_decider:
        write_rule = '你是清单确定者，但用户尚未确认，禁止输出 action JSON。'
    else:
        write_rule = '你不是确定者，只讨论、禁止输出 upsert_requirements / action JSON。'
    return f'{role}\n规则：\n1. 用中文简短回复。\n2. {round_rule}\n3. {write_rule}\n4. 不要泄露密钥或编造已上线功能。'


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
        bots = await cls.list_runtime_bots(query_db)
        for bot in bots:
            members.append(
                {
                    'userId': 0,
                    'userName': bot['userName'],
                    'nickName': bot['nickName'],
                    'role': 'ai',
                    'isDecider': bot['isDecider'],
                }
            )
        return {
            'roomId': 1,
            'title': '需求沟通',
            'excluded': sorted(EXCLUDED_USERNAMES),
            'members': members,
            'ai': bots[0] if bots else dict(DEFAULT_AI_USER),
            'bots': bots,
            'maxRounds': MAX_ROUNDS,
        }

    @classmethod
    async def history_services(cls, query_db: AsyncSession, after_id: int = 0, limit: int = 200) -> dict[str, Any]:
        rows = await AiReqDao.list_messages(query_db, after_id=after_id, limit=limit)
        return {'items': [cls.serialize_message(r) for r in rows], 'count': len(rows)}

    @classmethod
    def serialize_bot(cls, row: Any) -> dict[str, Any]:
        return {
            'botId': row.bot_id,
            'modelId': row.model_id,
            'displayName': row.display_name,
            'enabled': row.enabled == '1',
            'isDecider': row.is_decider == '1',
            'sortOrder': row.sort_order or 0,
        }

    @classmethod
    async def list_bots_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        models = (await query_db.execute(select(AiModels).where(AiModels.status == '0'))).scalars().all()
        bots = [cls.serialize_bot(r) for r in await AiReqDao.list_bots(query_db)]
        return {
            'bots': bots,
            'models': [
                {
                    'modelId': m.model_id,
                    'modelName': m.model_name,
                    'modelCode': m.model_code,
                    'provider': m.provider,
                }
                for m in models
            ],
            'fallback': dict(DEFAULT_AI_USER),
        }

    @classmethod
    async def save_bots_services(cls, query_db: AsyncSession, payload: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
        raw = payload.get('bots') if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            raise ServiceException(message='机器人配置必须是列表')
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for index, item in enumerate(raw or []):
            if not isinstance(item, dict):
                continue
            model_id = int(item.get('modelId') or item.get('model_id') or 0)
            if not model_id or model_id in seen:
                continue
            seen.add(model_id)
            enabled = '1' if item.get('enabled') in {True, '1', 1, 'true'} else '0'
            is_decider = '1' if item.get('isDecider') in {True, '1', 1, 'true'} else '0'
            name = str(item.get('displayName') or item.get('display_name') or '').strip()[:64]
            if not name:
                name = f'AI-{model_id}'
            rows.append(
                {
                    'model_id': model_id,
                    'display_name': name,
                    'enabled': enabled,
                    'is_decider': is_decider,
                    'sort_order': int(item.get('sortOrder') or index),
                    'create_time': datetime.now(),
                    'update_time': datetime.now(),
                }
            )
        enabled_rows = [r for r in rows if r['enabled'] == '1']
        deciders = [r for r in enabled_rows if r['is_decider'] == '1']
        if enabled_rows and len(deciders) != 1:
            raise ServiceException(message='必须在已勾选成员中指定唯一清单确定者')
        for row in rows:
            if row['is_decider'] == '1' and row['enabled'] != '1':
                raise ServiceException(message='确定者必须是已勾选的参与者')
        await AiReqDao.replace_bots(query_db, rows)
        await query_db.commit()
        return await cls.list_bots_services(query_db)

    @classmethod
    async def list_runtime_bots(cls, query_db: AsyncSession) -> list[dict[str, Any]]:
        rows = await AiReqDao.list_enabled_bots(query_db)
        if not rows:
            return [dict(DEFAULT_AI_USER)]
        out = []
        for row in rows:
            out.append(
                {
                    'botId': row.bot_id,
                    'modelId': row.model_id,
                    'userName': f'bot-{row.bot_id}',
                    'nickName': row.display_name,
                    'role': 'ai',
                    'isDecider': row.is_decider == '1',
                    'sortOrder': row.sort_order or 0,
                }
            )
        if not any(b['isDecider'] for b in out):
            out[0]['isDecider'] = True
        return out

    @classmethod
    def infer_round(cls, history: list[Any]) -> int:
        waves = 0
        prev = None
        for item in history:
            role = item.get('role') if isinstance(item, dict) else getattr(item, 'role', None)
            if role == 'ai' and prev != 'ai':
                waves += 1
            prev = role
        return min(max(waves + 1, 1), MAX_ROUNDS)

    @classmethod
    def is_confirm_text(cls, text: str) -> bool:
        raw = (text or '').strip()
        if raw in CONFIRM_EXACT:
            return True
        return bool(CONFIRM_RE.search(raw))

    @classmethod
    async def _resolve_model(cls, query_db: AsyncSession, model_id: int | None) -> dict[str, Any]:
        if not model_id:
            return await cls._resolve_grok(query_db)
        model = (await query_db.execute(select(AiModels).where(AiModels.model_id == int(model_id)))).scalars().first()
        if not model or not (model.base_url and model.api_key and model.model_code):
            return {'available': False}
        try:
            api_key = CryptoUtil.decrypt(model.api_key) if model.api_key else None
        except Exception:
            api_key = model.api_key
        return {
            'available': bool(model.base_url and api_key and model.model_code),
            'baseUrl': model.base_url,
            'apiKey': api_key,
            'modelName': model.model_code,
            'provider': model.provider,
        }

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
    async def _call_model(
        cls,
        conf: dict[str, Any],
        history: list[dict[str, str]],
        user_text: str,
        system: str,
    ) -> str:
        url = str(conf['baseUrl']).rstrip('/')
        if not url.endswith('/chat/completions'):
            url = f'{url}/chat/completions'
        messages = [{'role': 'system', 'content': system}]
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
            existing = await AiReqDao.get_item_by_title(query_db, item['title'])
            if existing:
                await AiReqDao.update_item(
                    query_db,
                    existing.item_id,
                    {
                        'detail': item.get('detail') or existing.detail,
                        'priority': item.get('priority') or existing.priority or 'P2',
                        'source_msg_id': source_msg_id or existing.source_msg_id,
                    },
                )
                row = await AiReqDao.get_item(query_db, existing.item_id)
            else:
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
        user_name: str = 'grok',
        nick_name: str = 'Grok',
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        ai_row = await AiReqDao.add_message(
            query_db,
            {
                'room_id': 1,
                'user_id': 0,
                'user_name': user_name,
                'nick_name': nick_name,
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
        confirmed = cls.is_confirm_text(text) or bool(payload.get('summarize'))
        history_rows = await AiReqDao.list_messages(query_db, after_id=0, limit=40)
        history = [
            {'role': r.role, 'content': r.content, 'nickName': r.nick_name}
            for r in history_rows
            if r.msg_id != user_msg_id
        ]
        return await cls._run_parallel_round(
            query_db,
            history=history,
            user_text=f'{nick_name or user_name}: {text}',
            created_by=user_id,
            created_by_name=nick_name or user_name,
            confirmed=confirmed,
            summarize=bool(payload.get('summarize')),
        )

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
            'message': '已加入后台队列，确定者总结完成后会写入清单',
        }

    @classmethod
    async def process_summarize_job(cls, query_db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        payload = {**payload, 'summarize': True}
        result = await cls.process_send_job(query_db, payload)
        count = int(result.get('count') or 0)
        result['message'] = f'已写入 {count} 条需求' if count else '未解析到可写入的确定需求'
        return result

    @classmethod
    def _peer_notes(cls, history: list[dict[str, str]]) -> str:
        notes = []
        for item in reversed(history):
            if item.get('role') != 'ai':
                if notes:
                    break
                continue
            name = item.get('nickName') or 'AI'
            notes.append(f'- {name}: {(item.get("content") or "")[:280]}')
            if len(notes) >= 8:
                break
        notes.reverse()
        return '\n'.join(notes)

    @classmethod
    async def _run_parallel_round(
        cls,
        query_db: AsyncSession,
        history: list[dict[str, str]],
        user_text: str,
        created_by: int | None,
        created_by_name: str | None,
        confirmed: bool,
        summarize: bool,
    ) -> dict[str, Any]:
        bots = await cls.list_runtime_bots(query_db)
        round_no = cls.infer_round(history)
        peer_notes = cls._peer_notes(history)
        write_now = confirmed or summarize
        prepared: list[tuple[dict[str, Any], dict[str, Any], str]] = []
        for bot in bots:
            is_decider = bool(bot.get('isDecider'))
            conf = await cls._resolve_model(query_db, bot.get('modelId'))
            prompt = system_prompt(
                name=str(bot.get('nickName') or 'AI'),
                is_decider=is_decider,
                round_no=round_no,
                peer_notes=peer_notes,
                write_allowed=write_now and is_decider,
            )
            prepared.append((bot, conf, prompt))

        async def speak(bot: dict[str, Any], conf: dict[str, Any], prompt: str) -> tuple[dict[str, Any], str]:
            is_decider = bool(bot.get('isDecider'))
            if conf.get('available'):
                try:
                    reply = await cls._call_model(conf, history, user_text, prompt)
                except Exception as exc:
                    logger.warning(f'[需求沟通] {bot.get("nickName")} 调用失败: {exc}')
                    reply = f'{bot.get("nickName")} 暂时不可用：{exc}'
            else:
                reply = f'{bot.get("nickName")} 未配置可用模型，请在「AI 模型管理」补全后重试。'
            if (not is_decider or not write_now) and extract_requirement_payload(reply):
                reply = re.sub(
                    r'\{[\s\S]*"action"\s*:\s*"upsert_requirements"[\s\S]*\}',
                    '',
                    reply,
                ).strip() or reply
            return bot, reply

        pairs = await asyncio.gather(*[speak(bot, conf, prompt) for bot, conf, prompt in prepared])
        ai_messages: list[dict[str, Any]] = []
        written: list[dict[str, Any]] = []
        for bot, reply in pairs:
            is_decider = bool(bot.get('isDecider'))
            msg, items = await cls._append_ai_reply(
                query_db,
                reply,
                created_by=created_by,
                created_by_name=created_by_name,
                write_items=write_now and is_decider,
                user_name=str(bot.get('userName') or 'grok'),
                nick_name=str(bot.get('nickName') or 'Grok'),
            )
            ai_messages.append(msg)
            written.extend(items)
        if round_no >= MAX_ROUNDS and not write_now:
            notice, _ = await cls._append_ai_reply(
                query_db,
                f'已到默认 {MAX_ROUNDS} 轮。请确认后由确定者合并写入清单；更换确定者从下一轮生效。',
                created_by=created_by,
                created_by_name=created_by_name,
                write_items=False,
                user_name='system',
                nick_name='系统',
            )
            ai_messages.append(notice)
        return {
            'aiMessages': ai_messages,
            'aiMessage': ai_messages[-1] if ai_messages else None,
            'requirements': written,
            'count': len(written),
            'round': round_no,
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
