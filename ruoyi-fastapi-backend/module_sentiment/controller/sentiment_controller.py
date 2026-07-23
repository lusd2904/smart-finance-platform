from typing import Annotated

from fastapi import Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel, PageResponseModel, ResponseBaseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_sentiment.entity.vo.sentiment_vo import (
    DeleteSentimentNewsModel,
    SentimentAiConfigModel,
    SentimentAnalysisModel,
    SentimentAnalysisPageQueryModel,
    SentimentNewsModel,
    SentimentNewsPageQueryModel,
)
from module_sentiment.service.sentiment_service import SentimentService
from utils.log_util import logger
from utils.response_util import ResponseUtil

sentiment_controller = APIRouterPro(
    prefix='/sentiment', order_num=30, tags=['舆情分析'], dependencies=[PreAuthDependency()]
)


@sentiment_controller.get(
    '/news/list',
    summary='获取舆情资讯分页列表接口',
    description='用于获取舆情资讯分页列表',
    response_model=PageResponseModel[SentimentNewsModel],
    dependencies=[UserInterfaceAuthDependency('sentiment:news:list')],
)
async def get_sentiment_news_list(
    request: Request,
    news_page_query: Annotated[SentimentNewsPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    news_page_query_result = await SentimentService.get_news_list_services(query_db, news_page_query, is_page=True)
    logger.info('获取舆情资讯列表成功')

    return ResponseUtil.success(model_content=news_page_query_result)


@sentiment_controller.delete(
    '/news/{news_ids}',
    summary='删除舆情资讯接口',
    description='用于删除舆情资讯',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('sentiment:news:remove')],
)
@Log(title='舆情资讯', business_type=BusinessType.DELETE)
async def delete_sentiment_news(
    request: Request,
    news_ids: Annotated[str, Path(description='需要删除的资讯ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    delete_result = await SentimentService.delete_news_services(query_db, DeleteSentimentNewsModel(newsIds=news_ids))
    logger.info(delete_result.message)

    return ResponseUtil.success(msg=delete_result.message)


@sentiment_controller.post(
    '/news/collect',
    summary='手动触发舆情采集接口',
    description='立即执行一次舆情采集',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('sentiment:news:collect')],
)
@Log(title='舆情采集', business_type=BusinessType.OTHER)
async def collect_sentiment_news(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await SentimentService.collect_news_services(query_db)
    logger.info(f'手动采集完成: {result}')

    return ResponseUtil.success(data=result, msg=f'采集完成，抓取{result["fetched"]}条，新入库{result["saved"]}条')


@sentiment_controller.get(
    '/stats',
    summary='获取舆情统计数据接口',
    description='用于舆情大屏统计卡片',
    dependencies=[UserInterfaceAuthDependency('sentiment:news:list')],
)
async def get_sentiment_stats(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    stats = await SentimentService.get_stats_services(query_db)

    return ResponseUtil.success(data=stats)


@sentiment_controller.get(
    '/analysis/list',
    summary='获取舆情分析结果分页列表接口',
    description='用于获取AI分析结果分页列表',
    response_model=PageResponseModel[SentimentAnalysisModel],
    dependencies=[UserInterfaceAuthDependency('sentiment:analysis:list')],
)
async def get_sentiment_analysis_list(
    request: Request,
    analysis_page_query: Annotated[SentimentAnalysisPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    analysis_page_query_result = await SentimentService.get_analysis_list_services(
        query_db, analysis_page_query, is_page=True
    )
    logger.info('获取舆情分析结果列表成功')

    return ResponseUtil.success(model_content=analysis_page_query_result)


@sentiment_controller.get(
    '/analysis/trend',
    summary='获取舆情分析趋势接口',
    description='用于趋势图展示近期各市场影响分',
    dependencies=[UserInterfaceAuthDependency('sentiment:analysis:list')],
)
async def get_sentiment_analysis_trend(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    limit: Annotated[int, Query(description='返回条数')] = 24,
) -> Response:
    trend = await SentimentService.get_analysis_trend_services(query_db, limit)

    return ResponseUtil.success(data=trend)


@sentiment_controller.post(
    '/analysis/run',
    summary='手动触发AI分析接口',
    description='立即对未分析的舆情执行一次AI大盘影响分析',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('sentiment:analysis:run')],
)
@Log(title='舆情AI分析', business_type=BusinessType.OTHER)
async def run_sentiment_analysis(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await SentimentService.run_analysis_services(query_db)
    logger.info(f'手动分析完成: {result}')

    return ResponseUtil.success(data=result, msg=result['message'])


@sentiment_controller.get(
    '/analysis/{analysis_id}',
    summary='获取舆情分析结果详情接口',
    description='用于获取指定分析结果的详细信息',
    response_model=DataResponseModel[SentimentAnalysisModel],
    dependencies=[UserInterfaceAuthDependency('sentiment:analysis:query')],
)
async def query_sentiment_analysis_detail(
    request: Request,
    analysis_id: Annotated[int, Path(description='分析ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    analysis_detail = await SentimentService.get_analysis_detail_services(query_db, analysis_id)
    logger.info(f'获取analysis_id为{analysis_id}的信息成功')

    return ResponseUtil.success(data=analysis_detail)


@sentiment_controller.get(
    '/config',
    summary='获取舆情AI配置接口',
    description='用于获取AI分析配置（baseUrl/apiKey/模型等）',
    response_model=DataResponseModel[SentimentAiConfigModel],
    dependencies=[UserInterfaceAuthDependency('sentiment:config:query')],
)
async def get_sentiment_ai_config(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    config = await SentimentService.get_ai_config_services(query_db)

    return ResponseUtil.success(data=config)


@sentiment_controller.put(
    '/config',
    summary='保存舆情AI配置接口',
    description='用于保存AI分析配置',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('sentiment:config:edit')],
)
@Log(title='舆情AI配置', business_type=BusinessType.UPDATE)
async def save_sentiment_ai_config(
    request: Request,
    config: SentimentAiConfigModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    save_result = await SentimentService.save_ai_config_services(query_db, config, current_user.user.user_name)
    logger.info(save_result.message)

    return ResponseUtil.success(msg=save_result.message)
