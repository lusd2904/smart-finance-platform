from typing import Annotated

from fastapi import Body, Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import PageResponseModel, ResponseBaseModel
from module_quant.entity.vo.quant_vo import (
    AddQuantWatchlistModel,
    QuantLongbridgeConfigModel,
    QuantStrategyRunModel,
    QuantStrategyRunPageQueryModel,
    QuantWatchlistModel,
    QuantWatchlistPageQueryModel,
    RunStrategyModel,
)
from module_quant.service.quant_service import QuantService
from utils.log_util import logger
from utils.response_util import ResponseUtil

quant_controller = APIRouterPro(
    prefix='/quant', order_num=32, tags=['量化交易'], dependencies=[PreAuthDependency()]
)


# ---------------------------------------------------------------- 因子 ---


@quant_controller.get(
    '/factor/schema',
    summary='获取因子体系定义接口',
    description='返回8大因子族定义，供前端展示',
    dependencies=[UserInterfaceAuthDependency('quant:factor:list')],
)
async def get_factor_schema(request: Request) -> Response:
    schema = QuantService.get_factor_schema_services()
    return ResponseUtil.success(data=schema)


@quant_controller.get(
    '/factor/compute',
    summary='计算标的因子接口',
    description='根据历史K线计算某标的的因子值与综合打分',
    dependencies=[UserInterfaceAuthDependency('quant:factor:compute')],
)
async def compute_factor(
    request: Request,
    symbol: Annotated[str, Query(description='标的代码')],
    market: Annotated[str, Query(description='市场（US/HK/CN）')] = 'US',
    profile: Annotated[str, Query(description='策略档位')] = 'balanced',
) -> Response:
    result = await QuantService.compute_factor_services(symbol, market, profile)
    logger.info(f'计算标的{symbol}因子完成')
    return ResponseUtil.success(data=result)


# ---------------------------------------------------------------- 自选池 ---


@quant_controller.get(
    '/watchlist/list',
    summary='获取自选池分页列表接口',
    description='用于获取量化自选池分页列表',
    response_model=PageResponseModel[QuantWatchlistModel],
    dependencies=[UserInterfaceAuthDependency('quant:watchlist:list')],
)
async def get_watchlist_list(
    request: Request,
    watchlist_page_query: Annotated[QuantWatchlistPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await QuantService.get_watchlist_services(query_db, watchlist_page_query, is_page=True)
    logger.info('获取自选池列表成功')
    return ResponseUtil.success(model_content=result)


@quant_controller.post(
    '/watchlist',
    summary='新增自选标的接口',
    description='向量化自选池新增标的',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('quant:watchlist:add')],
)
@Log(title='量化自选池', business_type=BusinessType.INSERT)
async def add_watchlist(
    request: Request,
    add_model: AddQuantWatchlistModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await QuantService.add_watchlist_services(query_db, add_model)
    logger.info(result.message)
    return ResponseUtil.success(msg=result.message)


@quant_controller.delete(
    '/watchlist/{ids}',
    summary='删除自选标的接口',
    description='从量化自选池删除标的',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('quant:watchlist:remove')],
)
@Log(title='量化自选池', business_type=BusinessType.DELETE)
async def delete_watchlist(
    request: Request,
    ids: Annotated[str, Path(description='需要删除的自选ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await QuantService.delete_watchlist_services(query_db, ids)
    logger.info(result.message)
    return ResponseUtil.success(msg=result.message)


# ---------------------------------------------------------------- 策略 ---


@quant_controller.post(
    '/strategy/run',
    summary='触发策略运行接口',
    description='对自选池或指定标的跑一次策略并产出信号入库',
    dependencies=[UserInterfaceAuthDependency('quant:strategy:run')],
)
@Log(title='量化策略运行', business_type=BusinessType.OTHER)
async def run_strategy(
    request: Request,
    run_model: Annotated[RunStrategyModel, Body()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await QuantService.run_strategy_services(query_db, run_model)
    logger.info(f'策略运行完成: {result.get("message")}')
    return ResponseUtil.success(data=result, msg=result.get('message'))


@quant_controller.get(
    '/strategy/history',
    summary='获取策略运行历史接口',
    description='用于获取量化策略运行历史分页列表',
    response_model=PageResponseModel[QuantStrategyRunModel],
    dependencies=[UserInterfaceAuthDependency('quant:strategy:history')],
)
async def get_strategy_history(
    request: Request,
    run_page_query: Annotated[QuantStrategyRunPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await QuantService.get_strategy_history_services(query_db, run_page_query, is_page=True)
    logger.info('获取策略运行历史成功')
    return ResponseUtil.success(model_content=result)


@quant_controller.get(
    '/scan-runs',
    summary='扫描运行台账列表',
    description='只读展示策略扫描周期记录（最近N条）',
    dependencies=[UserInterfaceAuthDependency('quant:scan:list')],
)
async def get_scan_runs(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    limit: Annotated[int, Query(description='条数 20/50/100')] = 20,
) -> Response:
    result = await QuantService.get_scan_runs_services(query_db, limit=limit)
    return ResponseUtil.success(data=result)


@quant_controller.get(
    '/scan-runs/{cycle_id}',
    summary='扫描运行详情',
    description='含候选/机会/跳过明细',
    dependencies=[UserInterfaceAuthDependency('quant:scan:query')],
)
async def get_scan_run_detail(
    request: Request,
    cycle_id: Annotated[str, Path(description='cycle_id 或 run_id')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await QuantService.get_scan_run_detail_services(query_db, cycle_id)
    return ResponseUtil.success(data=result)


@quant_controller.get(
    '/symbols/{symbol}/latest',
    summary='标的最新扫描与AI研判',
    dependencies=[UserInterfaceAuthDependency('quant:scan:query')],
)
async def get_symbol_latest_scan(
    request: Request,
    symbol: Annotated[str, Path()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query()] = 'US',
) -> Response:
    result = await QuantService.get_symbol_latest_scan_services(query_db, symbol, market)
    return ResponseUtil.success(data=result)


# ---------------------------------------------------------------- 长桥 ---


@quant_controller.get(
    '/longbridge/test',
    summary='长桥连通性测试接口',
    description='测试长桥凭据配置与连接状态',
    dependencies=[UserInterfaceAuthDependency('quant:longbridge:test')],
)
async def test_longbridge(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await QuantService.test_longbridge_services(query_db)
    return ResponseUtil.success(data=result)


@quant_controller.get(
    '/longbridge/config',
    summary='获取长桥凭据配置接口',
    description='获取长桥凭据配置（敏感字段脱敏）',
    dependencies=[UserInterfaceAuthDependency('quant:longbridge:config')],
)
async def get_longbridge_config(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    config = await QuantService.get_longbridge_config_services(query_db)
    return ResponseUtil.success(data=config)


@quant_controller.put(
    '/longbridge/config',
    summary='保存长桥凭据配置接口',
    description='保存长桥凭据配置，保存后DB凭据优先于env生效',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('quant:longbridge:config')],
)
@Log(title='长桥凭据配置', business_type=BusinessType.UPDATE)
async def save_longbridge_config(
    request: Request,
    config: QuantLongbridgeConfigModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await QuantService.save_longbridge_config_services(query_db, config)
    logger.info(result.message)
    return ResponseUtil.success(msg=result.message)
