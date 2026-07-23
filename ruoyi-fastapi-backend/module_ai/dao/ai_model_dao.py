from typing import Any

from sqlalchemy import ColumnElement, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from module_ai.entity.do.ai_model_do import AiModels
from module_ai.entity.vo.ai_model_vo import AiModelModel, AiModelPageQueryModel
from utils.page_util import PageUtil


class AiModelDao:
    """
    AI模型管理数据库操作层
    """

    @classmethod
    async def get_ai_model_detail_by_id(cls, db: AsyncSession, model_id: int) -> AiModels | None:
        """
        根据AI模型id获取AI模型详细信息

        :param db: orm对象
        :param model_id: AI模型id
        :return: AI模型信息对象
        """
        ai_model_info = (await db.execute(select(AiModels).where(AiModels.model_id == model_id))).scalars().first()

        return ai_model_info

    @classmethod
    async def get_ai_model_list(
        cls, db: AsyncSession, query_object: AiModelPageQueryModel, data_scope_sql: ColumnElement, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取AI模型列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :param is_page: 是否开启分页
        :return: AI模型列表信息对象
        """
        query = (
            select(AiModels)
            .where(
                AiModels.model_id == query_object.model_id if query_object.model_id else True,
                AiModels.model_name.like(f'%{query_object.model_name}%') if query_object.model_name else True,
                AiModels.model_code.like(f'%{query_object.model_code}%') if query_object.model_code else True,
                AiModels.provider == query_object.provider if query_object.provider else True,
                AiModels.status == query_object.status if query_object.status else True,
                data_scope_sql,
            )
            .order_by(AiModels.model_sort)
        )
        ai_model_list: PageModel | list[dict[str, Any]] = await PageUtil.paginate(
            db, query, query_object.page_num, query_object.page_size, is_page
        )

        return ai_model_list

    @classmethod
    async def get_ai_model_by_scope(cls, db: AsyncSession, scope: str) -> AiModels | None:
        """
        根据适用范围(scope)获取AI模型配置(取第一条)

        :param db: orm对象
        :param scope: 适用范围(chat/sentiment/quant/global)
        :return: AI模型信息对象
        """
        ai_model_info = (
            (
                await db.execute(
                    select(AiModels)
                    .where(AiModels.scope == scope, AiModels.status == '0')
                    .order_by(AiModels.model_sort, AiModels.model_id)
                )
            )
            .scalars()
            .first()
        )

        return ai_model_info

    @classmethod
    async def resolve_ai_model_for_business(cls, db: AsyncSession, preferred_scope: str = 'sentiment') -> AiModels | None:
        """
        业务模块解析可用 AI 模型：按 preferred_scope -> global -> chat -> 任意启用模型 回退。
        解决「只在 AI 管理里配了 chat 模型，舆情/行情读不到」的问题。
        """
        scopes = [preferred_scope, 'global', 'chat']
        seen: set[str] = set()
        for scope in scopes:
            if not scope or scope in seen:
                continue
            seen.add(scope)
            model = await cls.get_ai_model_by_scope(db, scope)
            if model and (model.base_url and model.api_key and model.model_code):
                return model
        # 任意启用且三要素齐全的模型
        row = (
            (
                await db.execute(
                    select(AiModels)
                    .where(AiModels.status == '0')
                    .order_by(AiModels.model_sort, AiModels.model_id)
                )
            )
            .scalars()
            .all()
        )
        for model in row:
            if model.base_url and model.api_key and model.model_code:
                return model
        return None

    @classmethod
    async def upsert_ai_model_by_scope(cls, db: AsyncSession, scope: str, values: dict) -> AiModels:
        """
        按适用范围(scope)新增或更新唯一一条AI模型配置(get-or-create模式)，
        用于其他业务模块(如舆情、行情)复用同一份AI连接配置而无需暴露完整的AI模型管理列表

        :param db: orm对象
        :param scope: 适用范围(chat/sentiment/quant/global)
        :param values: 需要写入的字段字典
        :return: AI模型信息对象
        """
        existing = await cls.get_ai_model_by_scope(db, scope)
        if existing:
            update_values = {**values, 'model_id': existing.model_id}
            await db.execute(update(AiModels), [update_values])
            await db.flush()
            return await cls.get_ai_model_detail_by_id(db, existing.model_id)

        default_values = {
            'scope': scope,
            'provider': 'OpenAI',
            'model_code': '',
            'model_sort': 0,
            'status': '0',
        }
        default_values.update(values)
        db_model = AiModels(**default_values)
        db.add(db_model)
        await db.flush()

        return db_model

    @classmethod
    async def add_ai_model_dao(cls, db: AsyncSession, ai_model: AiModelModel) -> AiModels:
        """
        新增AI模型数据库操作

        :param db: orm对象
        :param ai_model: AI模型对象
        :return: AI模型信息对象
        """
        db_model = AiModels(**ai_model.model_dump(exclude_unset=True))
        db.add(db_model)
        await db.flush()

        return db_model

    @classmethod
    async def edit_ai_model_dao(cls, db: AsyncSession, ai_model: dict) -> None:
        """
        编辑AI模型数据库操作

        :param db: orm对象
        :param ai_model: 需要更新的AI模型字典
        :return:
        """
        await db.execute(update(AiModels), [ai_model])

    @classmethod
    async def delete_ai_model_dao(cls, db: AsyncSession, ai_model: AiModelModel) -> None:
        """
        删除AI模型数据库操作

        :param db: orm对象
        :param ai_model: AI模型对象
        :return:
        """
        await db.execute(delete(AiModels).where(AiModels.model_id.in_([ai_model.model_id])))
