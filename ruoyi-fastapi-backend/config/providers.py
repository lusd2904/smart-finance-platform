"""
跨层缓存装配协议。

架构约束：公共层（config/*）不允许直接依赖业务模块（module_admin 等）。
字典/参数缓存的真正实现由各进程启动入口通过 install_module_admin_provider()
注入；未装配时回退 EnvFallbackProvider（告警并跳过），保证极早期启动与
未装配进程（如部分 CLI 子命令）不会因缺依赖而崩溃。
"""

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.entity.vo.user_vo import CurrentUserModel
from utils.log_util import logger

if TYPE_CHECKING:
    from redis.asyncio.client import Redis


class CacheWarmProvider(Protocol):
    """字典/参数缓存预热协议。"""

    async def warm_dict_cache(self, redis: 'Redis') -> None:
        """刷新字典表缓存。"""
        ...

    async def warm_config_cache(self, redis: 'Redis') -> None:
        """刷新参数配置表缓存。"""
        ...


class EnvFallbackProvider:
    """未装配真实实现时的兜底：告警并跳过，不中断调用方流程。"""

    async def warm_dict_cache(self, redis: 'Redis') -> None:
        logger.warning('⚠️ 缓存预热提供者未装配（config/providers），跳过字典缓存刷新')

    async def warm_config_cache(self, redis: 'Redis') -> None:
        logger.warning('⚠️ 缓存预热提供者未装配（config/providers），跳过参数配置缓存刷新')


class ModuleAdminCacheWarmProvider:
    """
    真实实现适配器。

    module_admin 仅在方法体内延迟导入：config 层的模块加载图不包含任何
    业务模块，同时运行行为与改造前完全一致。
    """

    async def warm_dict_cache(self, redis: 'Redis') -> None:
        from config.database import AsyncSessionLocal
        from module_admin.service.dict_service import DictDataService

        async with AsyncSessionLocal() as session:
            await DictDataService.init_cache_sys_dict_services(session, redis)

    async def warm_config_cache(self, redis: 'Redis') -> None:
        from config.database import AsyncSessionLocal
        from module_admin.service.config_service import ConfigService

        async with AsyncSessionLocal() as session:
            await ConfigService.init_cache_sys_config_services(session, redis)


_provider: CacheWarmProvider | None = None


def set_cache_warm_provider(provider: CacheWarmProvider) -> None:
    """进程级注册缓存预热实现（后注册覆盖，供测试与入口装配使用）。"""
    global _provider  # noqa: PLW0603 - 进程级单例注册器
    _provider = provider


def get_cache_warm_provider() -> CacheWarmProvider:
    """获取当前提供者；未注册时返回 EnvFallbackProvider 兜底。"""
    return _provider if _provider is not None else EnvFallbackProvider()


def install_module_admin_provider() -> None:
    """启动入口一键装配真实实现（server / scheduler_server / CLI 缓存命令）。"""
    set_cache_warm_provider(ModuleAdminCacheWarmProvider())
    set_token_auth_provider(ModuleAdminTokenAuthProvider())
    set_operation_log_sink(ModuleAdminOperationLogSink())
    set_data_scope_tables_provider(ModuleAdminDataScopeTablesProvider())
    set_scheduler_persistence(ModuleAdminSchedulerJobPersistence())



# ---------------------------------------------------------------------------
# 令牌认证协议（common/aspect/pre_auth 使用）
# ---------------------------------------------------------------------------


class TokenAuthProvider(Protocol):
    """根据请求与令牌解析当前登录用户。"""

    async def get_current_user(self, request: Request, token: str, db: AsyncSession) -> CurrentUserModel:
        """校验令牌并返回当前用户信息。"""
        ...


class ModuleAdminTokenAuthProvider:
    """
    真实实现适配器。

    module_admin 仅在方法体内延迟导入，config 层的模块加载图不包含业务模块。
    同时作为未显式装配时的默认实现，保证行为与改造前一致。
    """

    async def get_current_user(self, request: Request, token: str, db: AsyncSession) -> CurrentUserModel:
        from module_admin.service.login_service import LoginService

        return await LoginService.get_current_user(request, token, db)


_token_auth_provider: TokenAuthProvider | None = None


def set_token_auth_provider(provider: TokenAuthProvider) -> None:
    """进程级注册令牌认证实现（后注册覆盖，供测试与入口装配使用）。"""
    global _token_auth_provider  # noqa: PLW0603 - 进程级单例注册器
    _token_auth_provider = provider


def get_token_auth_provider() -> TokenAuthProvider:
    """获取当前认证提供者；未注册时返回模块管理端默认适配器。"""
    return _token_auth_provider if _token_auth_provider is not None else ModuleAdminTokenAuthProvider()


# ---------------------------------------------------------------------------
# 操作/登录日志队列协议（common/annotation/log_annotation 使用）
# ---------------------------------------------------------------------------


class OperationLogSink(Protocol):
    """接收日志字段并落库（由业务侧负责构造模型与入队）。"""

    async def enqueue_login_log(self, request: Request, login_log_fields: dict[str, Any], func_path: str) -> None:
        """记录登录日志，字段为 LogininforModel 的别名键值。"""
        ...

    async def enqueue_operation_log(self, request: Request, oper_log_fields: dict[str, Any], func_path: str) -> None:
        """记录操作日志，字段为 OperLogModel 的别名键值。"""
        ...


class ModuleAdminOperationLogSink:
    """真实实现适配器：延迟导入 log_vo/log_service 构造模型并入队。"""

    async def enqueue_login_log(self, request: Request, login_log_fields: dict[str, Any], func_path: str) -> None:
        from module_admin.entity.vo.log_vo import LogininforModel
        from module_admin.service.log_service import LogQueueService

        await LogQueueService.enqueue_login_log(request, LogininforModel(**login_log_fields), func_path)

    async def enqueue_operation_log(self, request: Request, oper_log_fields: dict[str, Any], func_path: str) -> None:
        from module_admin.entity.vo.log_vo import OperLogModel
        from module_admin.service.log_service import LogQueueService

        await LogQueueService.enqueue_operation_log(request, OperLogModel(**oper_log_fields), func_path)


_operation_log_sink: OperationLogSink | None = None


def set_operation_log_sink(sink: OperationLogSink) -> None:
    """进程级注册日志落库实现（后注册覆盖，供测试与入口装配使用）。"""
    global _operation_log_sink  # noqa: PLW0603 - 进程级单例注册器
    _operation_log_sink = sink


def get_operation_log_sink() -> OperationLogSink:
    """获取当前日志落库提供者；未注册时返回模块管理端默认适配器。"""
    return _operation_log_sink if _operation_log_sink is not None else ModuleAdminOperationLogSink()


# ---------------------------------------------------------------------------
# 数据权限部门表协议（common/aspect/data_scope 使用）
# ---------------------------------------------------------------------------


class DataScopeTablesProvider(Protocol):
    """提供数据权限 SQL 构建所需的部门/角色部门 ORM 表。"""

    def dept_table(self) -> Any:
        """返回 SysDept 表对象。"""
        ...

    def role_dept_table(self) -> Any:
        """返回 SysRoleDept 表对象。"""
        ...


class ModuleAdminDataScopeTablesProvider:
    """真实实现适配器：延迟导入 module_admin 的部门相关 ORM 表。"""

    def dept_table(self) -> Any:
        from module_admin.entity.do.dept_do import SysDept

        return SysDept

    def role_dept_table(self) -> Any:
        from module_admin.entity.do.role_do import SysRoleDept

        return SysRoleDept


_data_scope_tables_provider: DataScopeTablesProvider | None = None


def set_data_scope_tables_provider(provider: DataScopeTablesProvider) -> None:
    """进程级注册数据权限表提供者（后注册覆盖，供测试与入口装配使用）。"""
    global _data_scope_tables_provider  # noqa: PLW0603 - 进程级单例注册器
    _data_scope_tables_provider = provider


def get_data_scope_tables_provider() -> DataScopeTablesProvider:
    """获取当前数据权限表提供者；未注册时返回模块管理端默认适配器。"""
    return _data_scope_tables_provider if _data_scope_tables_provider is not None else (
        ModuleAdminDataScopeTablesProvider()
    )


# ---------------------------------------------------------------------------
# 调度器任务持久化协议（config/scheduler/* 使用）
# ---------------------------------------------------------------------------


class SchedulerJobInfo(Protocol):
    """调度器视角的任务信息结构（由 JobModel 等实现满足属性访问）。"""

    @property
    def job_id(self) -> int | None: ...

    @property
    def job_name(self) -> str | None: ...

    @property
    def job_group(self) -> str | None: ...

    @property
    def job_executor(self) -> str | None: ...

    @property
    def invoke_target(self) -> str | None: ...

    @property
    def job_args(self) -> str | None: ...

    @property
    def job_kwargs(self) -> str | None: ...

    @property
    def cron_expression(self) -> str | None: ...

    @property
    def misfire_policy(self) -> str | None: ...

    @property
    def concurrent(self) -> str | None: ...

    @property
    def status(self) -> str | None: ...

    @property
    def update_time(self) -> datetime | None: ...


class SchedulerJobPersistence(Protocol):
    """调度器对任务表/任务日志表的持久化能力。"""

    async def get_all_jobs_for_scheduler(self, db: AsyncSession) -> Sequence[SchedulerJobInfo]:
        """获取全部任务（含暂停），供全量同步。"""
        ...

    async def get_jobs_for_scheduler(self, db: AsyncSession) -> Sequence[SchedulerJobInfo]:
        """获取应载入调度器的任务列表。"""
        ...

    async def get_job_detail_by_id(self, db: AsyncSession, job_id: int) -> Any:
        """按 ID 获取任务 ORM 行。"""
        ...

    def build_job_from_row(self, row: Any) -> SchedulerJobInfo:
        """将任务 ORM 行转换为调度器任务信息对象。"""
        ...

    def build_execution_log(self, **fields: Any) -> Any:
        """构建任务执行日志对象（键为模型别名）。"""
        ...

    def save_execution_log(self, db: AsyncSession, job_log: Any) -> Any:
        """保存任务执行日志。"""
        ...


class ModuleAdminSchedulerJobPersistence:
    """真实实现适配器：延迟导入 JobDao/JobLogService/job_vo。"""

    async def get_all_jobs_for_scheduler(self, db: AsyncSession) -> Sequence[SchedulerJobInfo]:
        from module_admin.dao.job_dao import JobDao

        return await JobDao.get_all_job_list_for_scheduler(db)

    async def get_jobs_for_scheduler(self, db: AsyncSession) -> Sequence[SchedulerJobInfo]:
        from module_admin.dao.job_dao import JobDao

        return await JobDao.get_job_list_for_scheduler(db)

    async def get_job_detail_by_id(self, db: AsyncSession, job_id: int) -> Any:
        from module_admin.dao.job_dao import JobDao

        return await JobDao.get_job_detail_by_id(db, job_id)

    def build_job_from_row(self, row: Any) -> SchedulerJobInfo:
        from module_admin.entity.vo.job_vo import JobModel

        return JobModel.model_validate(row)

    def build_execution_log(self, **fields: Any) -> Any:
        from module_admin.entity.vo.job_vo import JobLogModel

        return JobLogModel(**fields)

    def save_execution_log(self, db: AsyncSession, job_log: Any) -> Any:
        from module_admin.service.job_log_service import JobLogService

        return JobLogService.add_job_log_services(db, job_log)


_scheduler_persistence: SchedulerJobPersistence | None = None


def set_scheduler_persistence(persistence: SchedulerJobPersistence) -> None:
    """进程级注册调度持久化实现（后注册覆盖，供测试与入口装配使用）。"""
    global _scheduler_persistence  # noqa: PLW0603 - 进程级单例注册器
    _scheduler_persistence = persistence


def get_scheduler_persistence() -> SchedulerJobPersistence:
    """获取当前调度持久化提供者；未注册时返回模块管理端默认适配器。"""
    return _scheduler_persistence if _scheduler_persistence is not None else ModuleAdminSchedulerJobPersistence()
