# Common Service templates for market, quant, sentiment, trade modules
# Extracted from module_market, module_quant, module_sentiment, module_trade

from typing import List, Optional, Type, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

T = TypeVar("T")

class BaseService:
    """Base Service template for all modules"""
    dao: Type = None

    def __init__(self, db: AsyncSession, dao):
        self.db = db
        self.dao = dao

    async def get(self, pk: int) -> Optional[T]:
        obj = await self.dao.get(pk)
        if not obj:
            raise HTTPException(status_code=404, detail="Not found")
        return obj

    async def get_by(self, **kwargs) -> Optional[T]:
        return await self.dao.get_by(**kwargs)

    async def list(self, **kwargs) -> List[T]:
        return await self.dao.list_all(**kwargs)

    async def create(self, obj_in: dict) -> T:
        return await self.dao.create(obj_in)

    async def update(self, pk: int, obj_in: dict) -> T:
        obj = await self.dao.update(pk, obj_in)
        if not obj:
            raise HTTPException(status_code=404, detail="Not found")
        return obj

    async def delete(self, pk: int) -> bool:
        success = await self.dao.delete(pk)
        if not success:
            raise HTTPException(status_code=404, detail="Not found")
        return success

    async def count(self) -> int:
        return await self.dao.count()

    # Bulk operations
    async def bulk_create(self, objs: List[dict]) -> List[T]:
        return await self.dao.bulk_create(objs)

    async def bulk_update(self, ids: List[int], updates: dict) -> int:
        return await self.dao.bulk_update(ids, updates)

    async def bulk_delete(self, ids: List[int]) -> int:
        return await self.dao.bulk_delete(ids)

# Module-specific Services will inherit from BaseService