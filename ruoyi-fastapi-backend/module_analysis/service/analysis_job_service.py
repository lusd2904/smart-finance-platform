from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from config.env import AppConfig
from exceptions.exception import ServiceException
from module_admin.dao.job_dao import JobDao
from module_admin.dao.job_log_dao import JobLogDao
from module_admin.entity.do.job_do import SysJob
from module_admin.entity.vo.job_vo import EditJobModel, JobLogPageQueryModel, JobModel
from module_admin.service.job_log_service import JobLogService
from module_admin.service.job_service import JobService
from module_task.analysis_catalog import (
    ANALYSIS_JOB_MAP,
    ANALYSIS_JOBS,
    AnalysisJobSpec,
    category_label,
    humanize_cron,
)
from utils.job_queue import JobQueue
from utils.scheduler_runtime import SchedulerRuntime

_TASK_CATEGORY = {
    'market_task': 'market',
    'quant_task': 'quant',
    'sentiment_task': 'sentiment',
    'trade_task': 'trade',
}


class AnalysisJobService:
    @classmethod
    async def get_overview(cls, query_db: AsyncSession) -> dict[str, Any]:
        heartbeat = await SchedulerRuntime.read_heartbeat()
        alive = SchedulerRuntime.is_alive(heartbeat)
        next_run_map = {
            str(item.get('jobId')): item.get('nextRunTime') for item in (heartbeat or {}).get('jobs') or []
        }
        db_jobs = await JobDao.get_jobs_by_ids(query_db, [spec.job_id for spec in ANALYSIS_JOBS])
        db_map = {int(job.job_id): job for job in db_jobs if job.job_id is not None}
        extra_jobs = await cls._extra_analysis_jobs(query_db, {spec.job_id for spec in ANALYSIS_JOBS})
        log_names = [spec.title for spec in ANALYSIS_JOBS] + [
            job.job_name for job in extra_jobs if job.job_name
        ]
        latest_logs = await JobLogDao.get_latest_logs_by_names(query_db, log_names)
        today_success, today_failed = await JobLogDao.count_today_by_names(query_db, log_names)

        jobs: list[dict[str, Any]] = []
        enabled_count = 0
        paused_count = 0
        missing_count = 0
        for spec in ANALYSIS_JOBS:
            db_job = db_map.get(spec.job_id)
            status = str(db_job.status) if db_job and db_job.status is not None else 'missing'
            if status == '0':
                enabled_count += 1
            elif status == '1':
                paused_count += 1
            else:
                missing_count += 1
            log = latest_logs.get(spec.title)
            if db_job and db_job.job_name:
                log = latest_logs.get(db_job.job_name, log)
            cron_expression = db_job.cron_expression if db_job and db_job.cron_expression else spec.default_cron
            jobs.append(
                {
                    'jobId': spec.job_id,
                    'code': spec.code,
                    'category': spec.category,
                    'categoryLabel': category_label(spec.category),
                    'title': spec.title,
                    'description': spec.description,
                    'invokeTarget': spec.invoke_target,
                    'cronExpression': cron_expression,
                    'scheduleLabel': humanize_cron(cron_expression) or spec.schedule_label,
                    'status': '1' if status == 'missing' else status,
                    'registered': db_job is not None,
                    'heavy': spec.heavy,
                    'queueType': spec.queue_type,
                    'remark': db_job.remark if db_job else spec.description,
                    'lastRunTime': log.create_time.strftime('%Y-%m-%d %H:%M:%S') if log and log.create_time else None,
                    'lastRunStatus': log.status if log else None,
                    'lastRunMessage': (log.job_message or log.exception_info) if log else None,
                    'nextRunTime': next_run_map.get(str(spec.job_id)),
                }
            )

        for job in extra_jobs:
            category = cls._category_from_target(str(job.invoke_target or ''))
            cron_expression = job.cron_expression or ''
            status = str(job.status) if job.status is not None else '1'
            if status == '0':
                enabled_count += 1
            else:
                paused_count += 1
            log = latest_logs.get(job.job_name or '')
            jobs.append(
                {
                    'jobId': int(job.job_id),
                    'code': f'custom_{job.job_id}',
                    'category': category,
                    'categoryLabel': category_label(category),
                    'title': job.job_name,
                    'description': job.remark or '平台自动分析任务',
                    'invokeTarget': job.invoke_target,
                    'cronExpression': cron_expression,
                    'scheduleLabel': humanize_cron(cron_expression),
                    'status': status,
                    'registered': True,
                    'heavy': True,
                    'queueType': None,
                    'remark': job.remark,
                    'lastRunTime': log.create_time.strftime('%Y-%m-%d %H:%M:%S') if log and log.create_time else None,
                    'lastRunStatus': log.status if log else None,
                    'lastRunMessage': (log.job_message or log.exception_info) if log else None,
                    'nextRunTime': next_run_map.get(str(job.job_id)),
                }
            )

        running = (heartbeat or {}).get('running') if alive else []
        queue_depth = int((heartbeat or {}).get('queueDepth') or 0) if alive else await JobQueue.depth()
        return {
            'schedulerAlive': alive,
            'appRole': AppConfig.app_role,
            'workerId': (heartbeat or {}).get('workerId'),
            'hostname': (heartbeat or {}).get('hostname'),
            'pid': (heartbeat or {}).get('pid'),
            'heartbeatAt': (heartbeat or {}).get('ts'),
            'queueDepth': queue_depth,
            'running': running or [],
            'enabledCount': enabled_count,
            'pausedCount': paused_count,
            'missingCount': missing_count,
            'todaySuccess': today_success,
            'todayFailed': today_failed,
            'jobs': jobs,
        }

    @classmethod
    def _category_from_target(cls, invoke_target: str) -> str:
        for module_name, category in _TASK_CATEGORY.items():
            if f'.{module_name}.' in invoke_target:
                return category
        return 'market'

    @classmethod
    def _is_analysis_target(cls, invoke_target: str) -> bool:
        target = str(invoke_target or '')
        if not target.startswith('module_task.') or 'scheduler_test' in target:
            return False
        return any(f'.{name}.' in target for name in _TASK_CATEGORY)

    @classmethod
    async def _extra_analysis_jobs(cls, query_db: AsyncSession, known_ids: set[int]) -> list[SysJob]:
        extras: list[SysJob] = []
        for job in await JobDao.get_all_job_list_for_scheduler(query_db):
            if job.job_id is None or int(job.job_id) in known_ids:
                continue
            if cls._is_analysis_target(str(job.invoke_target or '')):
                extras.append(job)
        extras.sort(key=lambda item: int(item.job_id))
        return extras

    @classmethod
    def _require_spec(cls, job_id: int) -> AnalysisJobSpec | None:
        return ANALYSIS_JOB_MAP.get(int(job_id))

    @classmethod
    async def _require_job(cls, query_db: AsyncSession, job_id: int) -> tuple[AnalysisJobSpec | None, JobModel]:
        spec = cls._require_spec(job_id)
        job_info = await JobService.job_detail_services(query_db, job_id)
        if job_info and job_info.job_id and cls._is_analysis_target(str(job_info.invoke_target or '')):
            return spec, job_info
        if spec:
            raise ServiceException(message=f'任务未注册到 sys_job：{spec.title}，请先执行 sql/analysis-scheduler.sql')
        raise ServiceException(message='不是平台自动分析任务')

    @classmethod
    async def change_status(cls, query_db: AsyncSession, job_id: int, status: str) -> None:
        if status not in {'0', '1'}:
            raise ServiceException(message='状态仅支持 0 启用 / 1 暂停')
        await cls._require_job(query_db, job_id)
        result = await JobService.edit_job_services(
            query_db,
            EditJobModel(jobId=job_id, status=status, type='status'),
        )
        if not result.is_success:
            raise ServiceException(message=result.message)

    @classmethod
    async def run_once(cls, query_db: AsyncSession, job_id: int) -> str:
        await cls._require_job(query_db, job_id)
        result = await JobService.execute_job_once_services(query_db, JobModel(jobId=job_id))
        if not result.is_success:
            raise ServiceException(message=result.message)
        return result.message

    @classmethod
    async def get_logs(
        cls, query_db: AsyncSession, job_id: int, page_num: int, page_size: int
    ) -> PageModel | list[dict[str, Any]]:
        spec, job_info = await cls._require_job(query_db, job_id)
        job_name = job_info.job_name if job_info and job_info.job_name else (spec.title if spec else str(job_id))
        return await JobLogService.get_job_log_list_services(
            query_db,
            JobLogPageQueryModel(job_name=job_name, page_num=page_num, page_size=page_size),
            is_page=True,
        )
