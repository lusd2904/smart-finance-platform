from typing import Annotated

from fastapi import Body, Header, Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from config.env import AppConfig
from exceptions.exception import ServiceException
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_ai.service.ai_req_service import AiReqService
from utils.job_queue import JobQueue
from utils.log_util import logger
from utils.response_util import ResponseUtil

ai_req_controller = APIRouterPro(
    prefix='/ai/req', order_num=20, tags=['AI管理-需求沟通'], dependencies=[PreAuthDependency()]
)

ai_req_open_controller = APIRouterPro(prefix='/open', order_num=91, tags=['对外-需求清单'])


def _user_fields(current_user: CurrentUserModel) -> tuple[int, str, str]:
    user = current_user.user if current_user else None
    user_id = int(getattr(user, 'user_id', 0) or 0)
    user_name = str(getattr(user, 'user_name', '') or '')
    nick_name = str(getattr(user, 'nick_name', '') or user_name)
    if not user_id or not user_name:
        raise ServiceException(message='无法识别当前用户')
    return user_id, user_name, nick_name


@ai_req_controller.get(
    '/bots',
    summary='需求沟通机器人配置',
    dependencies=[UserInterfaceAuthDependency('ai:req:bot')],
)
async def get_req_bots(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await AiReqService.list_bots_services(query_db))


@ai_req_controller.put(
    '/bots',
    summary='保存需求沟通机器人',
    dependencies=[UserInterfaceAuthDependency('ai:req:bot:edit')],
)
@Log(title='需求沟通机器人', business_type=BusinessType.UPDATE)
async def put_req_bots(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: Annotated[dict, Body()],
) -> Response:
    data = await AiReqService.save_bots_services(query_db, body)
    return ResponseUtil.success(data=data, msg='机器人配置已保存，下一轮讨论生效')


@ai_req_controller.get(
    '/room',
    summary='需求沟通群信息',
    dependencies=[UserInterfaceAuthDependency('ai:req:chat')],
)
async def get_req_room(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await AiReqService.room_services(query_db))


@ai_req_controller.get(
    '/messages',
    summary='需求沟通消息',
    dependencies=[UserInterfaceAuthDependency('ai:req:chat')],
)
async def get_req_messages(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    after_id: Annotated[int, Query()] = 0,
    limit: Annotated[int, Query()] = 200,
) -> Response:
    return ResponseUtil.success(data=await AiReqService.history_services(query_db, after_id=after_id, limit=limit))


@ai_req_controller.post(
    '/messages',
    summary='发送需求沟通消息',
    dependencies=[UserInterfaceAuthDependency('ai:req:chat')],
)
async def post_req_message(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    body: Annotated[dict, Body()],
) -> Response:
    user_id, user_name, nick_name = _user_fields(current_user)
    data = await AiReqService.enqueue_send_services(
        query_db, str(body.get('content') or ''), user_id, user_name, nick_name
    )
    logger.info(f'需求沟通消息已入队 user={user_name} jobId={data.get("jobId")}')
    return ResponseUtil.success(data=data, msg='已发送，Grok 正在后台回复')


@ai_req_controller.post(
    '/summarize',
    summary='总结确定需求并写入清单',
    dependencies=[UserInterfaceAuthDependency('ai:req:chat')],
)
@Log(title='需求沟通总结', business_type=BusinessType.OTHER)
async def post_req_summarize(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    user_id, user_name, nick_name = _user_fields(current_user)
    data = await AiReqService.enqueue_summarize_services(query_db, user_id, user_name, nick_name)
    logger.info(f'需求沟通总结已入队 user={user_name} jobId={data.get("jobId")}')
    return ResponseUtil.success(data=data, msg=data.get('message') or '已加入后台队列')


@ai_req_controller.get(
    '/jobs/{job_id}',
    summary='需求沟通后台任务状态',
    dependencies=[UserInterfaceAuthDependency('ai:req:chat')],
)
async def get_req_job(
    request: Request,
    job_id: Annotated[str, Path()],
) -> Response:
    ticket = await JobQueue.get_ticket(job_id)
    if not ticket:
        raise ServiceException(message='任务不存在或已过期')
    return ResponseUtil.success(data=ticket)


@ai_req_controller.get(
    '/items',
    summary='需求清单',
    dependencies=[UserInterfaceAuthDependency('ai:req:list')],
)
async def get_req_items(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    status: Annotated[str | None, Query()] = None,
) -> Response:
    return ResponseUtil.success(data=await AiReqService.list_items_services(query_db, status=status))


@ai_req_controller.put(
    '/items/{item_id}/status',
    summary='更新需求状态',
    dependencies=[UserInterfaceAuthDependency('ai:req:edit')],
)
@Log(title='需求清单状态', business_type=BusinessType.UPDATE)
async def put_req_item_status(
    request: Request,
    item_id: Annotated[int, Path()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: Annotated[dict, Body()],
) -> Response:
    data = await AiReqService.update_status_services(
        query_db, item_id, str(body.get('status') or ''), remark=body.get('remark')
    )
    return ResponseUtil.success(data=data, msg='状态已更新')


@ai_req_controller.get(
    '/items/export',
    summary='导出需求清单（登录）',
    dependencies=[UserInterfaceAuthDependency('ai:req:list')],
)
async def export_req_items(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    status: Annotated[str | None, Query()] = None,
) -> Response:
    return ResponseUtil.success(data=await AiReqService.export_services(query_db, status=status))


def _check_export_token(token: str | None) -> None:
    expected = (AppConfig.requirements_export_token or '').strip()
    if not expected:
        raise ServiceException(message='未配置 REQUIREMENTS_EXPORT_TOKEN，对外导出未开启')
    if (token or '').strip() != expected:
        raise ServiceException(message='导出令牌无效')


@ai_req_open_controller.get(
    '/requirements',
    summary='对外需求清单（Token）',
    description='Header: X-Req-Token。本地拉取后改代码并上传 git。',
)
async def open_requirements(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    status: Annotated[str | None, Query()] = None,
    x_req_token: Annotated[str | None, Header()] = None,
) -> Response:
    _check_export_token(x_req_token)
    data = await AiReqService.export_services(query_db, status=status)
    return ResponseUtil.success(data=data)
