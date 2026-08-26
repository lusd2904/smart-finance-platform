from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.parser import parse

BEIJING_TZ = ZoneInfo('Asia/Shanghai')
BEIJING_FMT = '%Y-%m-%d %H:%M:%S'
_TIME_KEYS = {
    'createTime',
    'create_time',
    'pubTime',
    'pub_time',
    'updateTime',
    'update_time',
    'analysisTime',
    'analysis_time',
}


def now_beijing() -> datetime:
    """当前北京墙上时钟（朴素 datetime，写入舆情 create_time 等）。"""
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def format_beijing_datetime(value: datetime | str | None, fmt: str = BEIJING_FMT) -> str | None:
    """
    将 datetime / ISO 字符串格式化为北京时间（Asia/Shanghai），不含 Z / 偏移。

    假设：舆情采集东财/新浪等中国源的朴素 pub_time 已是北京墙上时钟，不得再当 UTC +8。
    带 Z / 偏移的值按绝对时刻转到上海。
    """
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return ''
        try:
            parsed = parse(raw)
        except Exception:
            return raw.replace('T', ' ').replace('Z', '').split('+')[0][:19]
        return format_beijing_datetime(parsed, fmt)
    if not isinstance(value, datetime):
        return str(value)
    stamp = value if value.tzinfo is None else value.astimezone(BEIJING_TZ)
    if stamp.tzinfo is not None:
        stamp = stamp.replace(tzinfo=None)
    return stamp.strftime(fmt)


def format_utc_as_beijing(value: datetime | str | None, fmt: str = BEIJING_FMT) -> str | None:
    """
    把 UTC 时刻转成北京墙上时钟。仅给长桥 / Influx 等 UTC 源用。

    舆情必须继续走 format_beijing_datetime / apply_beijing_times / now_beijing：
    东财/新浪朴素 pub_time 已是北京墙上时钟，用本函数会错误 +8。
    """
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return ''
        try:
            parsed = parse(raw)
        except Exception:
            return raw.replace('T', ' ').replace('Z', '').split('+')[0][:19]
        return format_utc_as_beijing(parsed, fmt)
    if not isinstance(value, datetime):
        return str(value)
    stamp = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return stamp.astimezone(BEIJING_TZ).strftime(fmt)


def encode_api_datetime(value: datetime) -> str:
    """API JSON：aware UTC → 北京；naive 视为已是墙上时钟（库内中国源 / 未标时区）。"""
    formatted = format_beijing_datetime(value)
    return formatted or ''


def apply_beijing_times(obj: Any) -> Any:
    """递归把 payload 里的 datetime / 时间字段格式化为北京时间字符串。"""
    if isinstance(obj, datetime):
        return format_beijing_datetime(obj)
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        for key, value in obj.items():
            if key in _TIME_KEYS or isinstance(value, datetime):
                out[key] = format_beijing_datetime(value) if value not in (None, '') else value
            else:
                out[key] = apply_beijing_times(value)
        return out
    if isinstance(obj, list):
        return [apply_beijing_times(item) for item in obj]
    if hasattr(obj, 'rows'):
        obj.rows = apply_beijing_times(obj.rows)
        return obj
    return obj


def object_format_datetime(obj: Any) -> Any:
    """
    :param obj: 输入一个对象
    :return:对目标对象所有datetime类型的属性格式化
    """
    for attr in dir(obj):
        value = getattr(obj, attr)
        if isinstance(value, datetime):
            setattr(obj, attr, value.strftime('%Y-%m-%d %H:%M:%S'))
    return obj


def list_format_datetime(lst: list[Any]) -> list[Any]:
    """
    :param lst: 输入一个嵌套对象的列表
    :return: 对目标列表中所有对象的datetime类型的属性格式化
    """
    for obj in lst:
        for attr in dir(obj):
            value = getattr(obj, attr)
            if isinstance(value, datetime):
                setattr(obj, attr, value.strftime('%Y-%m-%d %H:%M:%S'))
    return lst


def format_datetime_dict_list(dicts: list[dict]) -> list[dict]:
    """
    递归遍历嵌套字典，并将 datetime 值转换为字符串格式

    :param dicts: 输入一个嵌套字典的列表
    :return: 对目标列表中所有字典的datetime类型的属性格式化
    """
    result = []

    for item in dicts:
        new_item = {}
        for k, v in item.items():
            if isinstance(v, dict):
                # 递归遍历子字典
                new_item[k] = format_datetime_dict_list([v])[0]
            elif isinstance(v, datetime):
                # 如果值是 datetime 类型，则格式化为字符串
                new_item[k] = v.strftime('%Y-%m-%d %H:%M:%S')
            else:
                # 否则保留原始值
                new_item[k] = v
        result.append(new_item)

    return result


class TimeFormatUtil:
    """
    时间格式化工具类
    """

    @classmethod
    def format_time(cls, time_info: str | datetime, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
        """
        格式化时间字符串或datetime对象为指定格式

        :param time_info: 时间字符串或datetime对象
        :param fmt: 格式化格式，默认为'%Y-%m-%d %H:%M:%S'
        :return: 格式化后的时间字符串
        """
        if isinstance(time_info, datetime):
            format_date = time_info.strftime(fmt)
        else:
            try:
                date = parse(time_info)
                format_date = date.strftime(fmt)
            except Exception:
                format_date = time_info

        return format_date

    @classmethod
    def parse_date(cls, time_str: str) -> date | str:
        """
        解析时间字符串提取日期部分

        :param time_str: 时间字符串
        :return: 日期部分
        """
        try:
            dt = parse(time_str)
            return dt.date()
        except Exception:
            return time_str

    @classmethod
    def format_time_dict(cls, time_dict: dict, fmt: str = '%Y-%m-%d %H:%M:%S') -> dict:
        """
        格式化时间字典

        :param time_dict: 时间字典
        :param fmt: 格式化格式，默认为'%Y-%m-%d %H:%M:%S'
        :return: 格式化后的时间字典
        """
        copy_time_dict = deepcopy(time_dict)
        for k, v in copy_time_dict.items():
            if isinstance(v, (str, datetime)):
                copy_time_dict[k] = cls.format_time(v, fmt)
            elif isinstance(v, dict):
                copy_time_dict[k] = cls.format_time_dict(v, fmt)
            elif isinstance(v, list):
                copy_time_dict[k] = cls.format_time_list(v, fmt)
            else:
                copy_time_dict[k] = v

        return copy_time_dict

    @classmethod
    def format_time_list(cls, time_list: list, fmt: str = '%Y-%m-%d %H:%M:%S') -> list:
        """
        格式化时间列表

        :param time_list: 时间列表
        :param fmt: 格式化格式，默认为'%Y-%m-%d %H:%M:%S'
        :return: 格式化后的时间列表
        """
        format_time_list = []
        for item in time_list:
            if isinstance(item, (str, datetime)):
                format_item = cls.format_time(item, fmt)
            elif isinstance(item, dict):
                format_item = cls.format_time_dict(item, fmt)
            elif isinstance(item, list):
                format_item = cls.format_time_list(item, fmt)
            else:
                format_item = item

            format_time_list.append(format_item)

        return format_time_list
