from datetime import datetime
from typing import Any

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module_admin.entity.do.user_do import SysUser
from module_ai.entity.do.ai_req_do import AiReqItem, AiReqMessage

EXCLUDED_USERNAMES = frozenset({'admin', 'niangao'})


class AiReqDao:
    @classmethod
    async def list_members(cls, db: AsyncSession) -> list[SysUser]:
        rows = (
            (
                await db.execute(
                    select(SysUser)
                    .where(SysUser.del_flag == '0', SysUser.status == '0')
                    .order_by(SysUser.user_id)
                )
            )
            .scalars()
            .all()
        )
        return [u for u in rows if (u.user_name or '').lower() not in EXCLUDED_USERNAMES]

    @classmethod
    async def add_message(cls, db: AsyncSession, item: dict[str, Any]) -> AiReqMessage:
        row = AiReqMessage(**item)
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    @classmethod
    async def list_messages(cls, db: AsyncSession, after_id: int = 0, limit: int = 200) -> list[AiReqMessage]:
        limit = max(1, min(int(limit or 200), 400))
        query = select(AiReqMessage).where(AiReqMessage.room_id == 1)
        if after_id:
            query = query.where(AiReqMessage.msg_id > int(after_id))
            query = query.order_by(AiReqMessage.msg_id.asc()).limit(limit)
        else:
            query = query.order_by(desc(AiReqMessage.msg_id)).limit(limit)
        rows = list((await db.execute(query)).scalars().all())
        if not after_id:
            rows.reverse()
        return rows

    @classmethod
    async def add_item(cls, db: AsyncSession, item: dict[str, Any]) -> AiReqItem:
        row = AiReqItem(**item)
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    @classmethod
    async def get_item(cls, db: AsyncSession, item_id: int) -> AiReqItem | None:
        return (await db.execute(select(AiReqItem).where(AiReqItem.item_id == item_id))).scalars().first()

    @classmethod
    async def list_items(cls, db: AsyncSession, status: str | None = None, limit: int = 200) -> list[AiReqItem]:
        limit = max(1, min(int(limit or 200), 500))
        query = select(AiReqItem)
        if status:
            query = query.where(AiReqItem.status == status)
        query = query.order_by(desc(AiReqItem.item_id)).limit(limit)
        return list((await db.execute(query)).scalars().all())

    @classmethod
    async def update_item(cls, db: AsyncSession, item_id: int, values: dict[str, Any]) -> bool:
        values = {**values, 'update_time': datetime.now()}
        res = await db.execute(update(AiReqItem).where(AiReqItem.item_id == item_id).values(**values))
        return (res.rowcount or 0) > 0
