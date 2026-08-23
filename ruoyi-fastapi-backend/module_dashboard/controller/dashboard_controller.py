from typing import Annotated

from fastapi import Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.entity.vo.user_vo import CurrentUserModel
from common.router import APIRouterPro
from common.vo import ResponseBaseModel
from module_dashboard.service.dashboard_service import DashboardService
from utils.response_util import ResponseUtil


def _current_user_id(current_user: CurrentUserModel) -> int | None:
    user = current_user.user if current_user else None
    user_id = getattr(user, 'user_id', None) if user else None
    return int(user_id) if user_id else None


dashboard_controller = APIRouterPro(
    prefix='/dashboard', order_num=29, tags=['工作台'], dependencies=[PreAuthDependency()]
)


@dashboard_controller.get(
    '/summary',
    summary='工作台均衡总览聚合',
    description=(
        '一次返回：三市场开闭市状态、账户资产、指数行情、三市场热度摘要、'
        '自选信号 Top5、舆情统计与最新研判、财经简报、运行状态。'
        '按当前用户权限逐块裁剪，无权限或无数据的块返回结构化空态。'
    ),
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('system:user:query')],
)
async def get_dashboard_summary(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    refresh: Annotated[bool, Query(description='跳过 30s 聚合缓存强制刷新')] = False,
) -> Response:
    summary = await DashboardService.get_summary_services(
        query_db,
        user_id=_current_user_id(current_user),
        permissions=current_user.permissions or [],
        use_cache=not refresh,
    )
    return ResponseUtil.success(data=summary)
