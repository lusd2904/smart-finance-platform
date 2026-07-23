from datetime import datetime, time
from typing import Any

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from module_sentiment.entity.do.sentiment_do import SentimentAiConfig, SentimentAnalysis, SentimentNews
from module_sentiment.entity.vo.sentiment_vo import (
    SentimentAnalysisPageQueryModel,
    SentimentNewsPageQueryModel,
)
from utils.page_util import PageUtil


class SentimentNewsDao:
    """
    舆情资讯数据库操作层
    """

    @classmethod
    async def get_news_list(
        cls, db: AsyncSession, query_object: SentimentNewsPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取舆情资讯列表
        """
        query = (
            select(SentimentNews)
            .where(
                SentimentNews.source == query_object.source if query_object.source else True,
                SentimentNews.title.like(f'%{query_object.title}%') if query_object.title else True,
                SentimentNews.analyzed == query_object.analyzed if query_object.analyzed else True,
                SentimentNews.create_time.between(
                    datetime.combine(datetime.strptime(query_object.begin_time, '%Y-%m-%d'), time(00, 00, 00)),
                    datetime.combine(datetime.strptime(query_object.end_time, '%Y-%m-%d'), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            .order_by(desc(SentimentNews.pub_time))
        )
        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_existing_hashes(cls, db: AsyncSession, hashes: list[str]) -> set[str]:
        """
        查询已存在的去重hash集合
        """
        if not hashes:
            return set()
        rows = (await db.execute(select(SentimentNews.uniq_hash).where(SentimentNews.uniq_hash.in_(hashes)))).all()
        return {row[0] for row in rows}

    @classmethod
    async def add_news_batch(cls, db: AsyncSession, news_list: list[dict]) -> list[SentimentNews]:
        """
        批量新增舆情资讯
        """
        db_news_list = [SentimentNews(**news) for news in news_list]
        db.add_all(db_news_list)
        await db.flush()
        return db_news_list

    @classmethod
    async def get_unanalyzed_news(cls, db: AsyncSession, limit: int = 30) -> list[SentimentNews]:
        """
        获取未分析的资讯（按发布时间倒序）
        """
        rows = (
            (
                await db.execute(
                    select(SentimentNews)
                    .where(SentimentNews.analyzed == '0')
                    .order_by(desc(SentimentNews.pub_time))
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    @classmethod
    async def mark_analyzed(cls, db: AsyncSession, news_ids: list[int]) -> None:
        """
        标记资讯为已分析
        """
        if not news_ids:
            return
        await db.execute(update(SentimentNews).where(SentimentNews.news_id.in_(news_ids)).values(analyzed='1'))

    @classmethod
    async def delete_news_dao(cls, db: AsyncSession, news_ids: list[int]) -> None:
        """
        删除舆情资讯
        """
        await db.execute(delete(SentimentNews).where(SentimentNews.news_id.in_(news_ids)))

    @classmethod
    async def count_news(cls, db: AsyncSession) -> dict[str, int]:
        """
        统计资讯总数与未分析数
        """
        total = (await db.execute(select(func.count(SentimentNews.news_id)))).scalar() or 0
        unanalyzed = (
            await db.execute(select(func.count(SentimentNews.news_id)).where(SentimentNews.analyzed == '0'))
        ).scalar() or 0
        today = (
            await db.execute(
                select(func.count(SentimentNews.news_id)).where(
                    SentimentNews.create_time >= datetime.combine(datetime.now().date(), time(0, 0, 0))
                )
            )
        ).scalar() or 0
        return {'total': total, 'unanalyzed': unanalyzed, 'today': today}


class SentimentAnalysisDao:
    """
    舆情AI分析结果数据库操作层
    """

    @classmethod
    async def get_analysis_list(
        cls, db: AsyncSession, query_object: SentimentAnalysisPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取分析结果列表
        """
        query = (
            select(SentimentAnalysis)
            .where(
                SentimentAnalysis.status == query_object.status if query_object.status else True,
                SentimentAnalysis.create_time.between(
                    datetime.combine(datetime.strptime(query_object.begin_time, '%Y-%m-%d'), time(00, 00, 00)),
                    datetime.combine(datetime.strptime(query_object.end_time, '%Y-%m-%d'), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            .order_by(desc(SentimentAnalysis.create_time))
        )
        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_analysis_by_id(cls, db: AsyncSession, analysis_id: int) -> SentimentAnalysis | None:
        """
        根据ID获取分析结果
        """
        return (
            (await db.execute(select(SentimentAnalysis).where(SentimentAnalysis.analysis_id == analysis_id)))
            .scalars()
            .first()
        )

    @classmethod
    async def get_latest_analysis(cls, db: AsyncSession) -> SentimentAnalysis | None:
        """
        获取最新一条成功的分析结果
        """
        return (
            (
                await db.execute(
                    select(SentimentAnalysis)
                    .where(SentimentAnalysis.status == '0')
                    .order_by(desc(SentimentAnalysis.create_time))
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_recent_analysis(cls, db: AsyncSession, limit: int = 24) -> list[SentimentAnalysis]:
        """
        获取最近N条成功的分析结果（用于趋势图）
        """
        rows = (
            (
                await db.execute(
                    select(SentimentAnalysis)
                    .where(SentimentAnalysis.status == '0')
                    .order_by(desc(SentimentAnalysis.create_time))
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    @classmethod
    async def add_analysis(cls, db: AsyncSession, analysis: dict) -> SentimentAnalysis:
        """
        新增分析结果
        """
        db_analysis = SentimentAnalysis(**analysis)
        db.add(db_analysis)
        await db.flush()
        return db_analysis


class SentimentAiConfigDao:
    """
    舆情AI配置数据库操作层
    """

    @classmethod
    async def get_config(cls, db: AsyncSession) -> SentimentAiConfig | None:
        """
        获取AI配置（单行）
        """
        return (
            (await db.execute(select(SentimentAiConfig).order_by(SentimentAiConfig.config_id).limit(1)))
            .scalars()
            .first()
        )

    @classmethod
    async def save_config(cls, db: AsyncSession, config: dict) -> SentimentAiConfig:
        """
        保存AI配置（存在则更新，不存在则新增）
        """
        existing = await cls.get_config(db)
        if existing:
            config['config_id'] = existing.config_id
            await db.execute(update(SentimentAiConfig), [config])
            await db.flush()
            return existing
        db_config = SentimentAiConfig(**{k: v for k, v in config.items() if k != 'config_id'})
        db.add(db_config)
        await db.flush()
        return db_config
