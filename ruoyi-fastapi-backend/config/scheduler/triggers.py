from datetime import datetime, timedelta

from apscheduler.triggers.cron import CronTrigger


# 重写Cron定时
class MyCronTrigger(CronTrigger):
    CRON_EXPRESSION_LENGTH_MIN = 6
    CRON_EXPRESSION_LENGTH_MAX = 7
    WEEKDAY_COUNT = 5

    @classmethod
    def from_crontab(cls, expr: str, timezone: str | None = None) -> 'MyCronTrigger':
        values = expr.split()
        if len(values) != cls.CRON_EXPRESSION_LENGTH_MIN and len(values) != cls.CRON_EXPRESSION_LENGTH_MAX:
            raise ValueError(f'Wrong number of fields; got {len(values)}, expected 6 or 7')

        second = values[0]
        minute = values[1]
        hour = values[2]
        if '?' in values[3]:
            day = None
        elif 'L' in values[5]:
            day = f'last {values[5].replace("L", "")}'
        elif 'W' in values[3]:
            day = cls.__find_recent_workday(int(values[3].split('W')[0]))
        else:
            day = values[3].replace('L', 'last')
        month = values[4]
        if '?' in values[5] or 'L' in values[5]:
            week = None
        elif '#' in values[5]:
            week = int(values[5].split('#')[1])
        else:
            week = values[5]
        day_of_week = int(values[5].split('#')[0]) - 1 if '#' in values[5] else None
        year = values[6] if len(values) == cls.CRON_EXPRESSION_LENGTH_MAX else None
        return cls(
            second=second,
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            week=week,
            day_of_week=day_of_week,
            year=year,
            timezone=timezone,
        )

    @classmethod
    def __find_recent_workday(cls, day: int) -> int:
        now = datetime.now()
        date = datetime(now.year, now.month, day)
        if date.weekday() < cls.WEEKDAY_COUNT:
            return date.day
        diff = 1
        while True:
            previous_day = date - timedelta(days=diff)
            if previous_day.weekday() < cls.WEEKDAY_COUNT:
                return previous_day.day
            diff += 1
