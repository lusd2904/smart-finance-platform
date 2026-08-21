from typing import Annotated

from fastapi import Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import PageResponseModel, ResponseBaseModel
from module_admin.entity.vo.job_vo import JobLogModel
from module_analysis.entity.vo.analysis_vo import AnalysisJobStatusModel
from module_analysis.service.analysis_job_service import AnalysisJobService
from utils.log_util import logger
from utils.response_util import ResponseUtil

analysis_controller = APIRouterPro(
    prefix='/analysis', order_num=28, tags=['自动分析任务'], dependencies=[PreAuthDependency()]
)


@analysis_controller.get(
    '/scheduler/overview',
    summary='自动分析任务总览',
    description='调度微服务心跳、队列深度与全部自动分析任务',
    dependencies=[UserInterfaceAuthDependency('analysis:job:list')],
)
async def get_analysis_scheduler_overview(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    overview = await AnalysisJobService.get_overview(query_db)
    logger.info('获取自动分析任务总览成功')
    return ResponseUtil.success(data=overview)


@analysis_controller.put(
    '/scheduler/jobs/{job_id}/status',
    summary='启用或暂停自动分析任务',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('analysis:job:edit')],
)
@Log(title='自动分析任务', business_type=BusinessType.UPDATE)
async def change_analysis_job_status(
    request: Request,
    job_id: Annotated[int, Path(description='任务ID')],
    body: AnalysisJobStatusModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    await AnalysisJobService.change_status(query_db, job_id, body.status)
    logger.info(f'更新分析任务 {job_id} 状态为 {body.status}')
    return ResponseUtil.success(msg='状态已更新，调度微服务将在数秒内同步')


@analysis_controller.post(
    '/scheduler/jobs/{job_id}/run',
    summary='立即执行一次自动分析任务',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('analysis:job:run')],
)
@Log(title='自动分析任务', business_type=BusinessType.UPDATE)
async def run_analysis_job_once(
    request: Request,
    job_id: Annotated[int, Path(description='任务ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    message = await AnalysisJobService.run_once(query_db, job_id)
    logger.info(f'提交分析任务 {job_id} 立即执行')
    return ResponseUtil.success(msg=message)


@analysis_controller.get(
    '/scheduler/jobs/{job_id}/logs',
    summary='自动分析任务执行日志',
    response_model=PageResponseModel[JobLogModel],
    dependencies=[UserInterfaceAuthDependency('analysis:job:query')],
)
async def get_analysis_job_logs(
    request: Request,
    job_id: Annotated[int, Path(description='任务ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    page_num: Annotated[int, Query(alias='pageNum')] = 1,
    page_size: Annotated[int, Query(alias='pageSize')] = 20,
) -> Response:
    result = await AnalysisJobService.get_logs(query_db, job_id, page_num, page_size)
    logger.info(f'获取分析任务 {job_id} 日志成功')
    return ResponseUtil.success(model_content=result)
