# Common DAO templates for market, quant, sentiment, trade modules
# Extracted from module_market, module_quant, module_sentiment, module_trade

from typing import Any, Type, TypeVar, List, Optional
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

T = TypeVar("T")

class BaseDAO:
    """Base DAO template for all modules"""
    model: Type[T] = None
    entity: Type[T] = None

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, pk: Any) -> Optional[T]:
        result = await self.session.get(self.model, pk)
        return result

    async def get_by(self, **kwargs) -> Optional[T]:
        stmt = select(self.model).filter_by(**kwargs)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> List[T]:
        result = await self.session.execute(select(self.model))
        return result.scalars().all()

    async def create(self, obj_in: dict) -> T:
        obj = self.model(**obj_in)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, pk: Any, obj_in: dict) -> T:
        db_obj = await self.get(pk)
        if not db_obj:
            return None
        for key, value in obj_in.items():
            setattr(db_obj, key, value)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, pk: Any) -> bool:
        obj = await self.get(pk)
        if not obj:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()

    # Common bulk operations
    async def bulk_create(self, objs: List[dict]) -> List[T]:
        instances = [self.model(**obj) for obj in objs]
        self.session.add_all(instances)
        await self.session.flush()
        for obj in instances:
            await self.session.refresh(obj)
        return instances

    async def bulk_update(self, ids: List[Any], updates: dict) -> int:
        stmt = update(self.model).where(self.model.id.in_(ids)).values(**updates)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def bulk_delete(self, ids: List[Any]) -> int:
        stmt = delete(self.model).where(self.model.id.in_(ids))
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

# Module-specific DAOs will inherit from BaseDAO