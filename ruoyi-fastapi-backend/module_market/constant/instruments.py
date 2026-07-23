"""
行情数据中心目标标的清单（常量）。

category 取值：
- index         美股三大指数（道指/标普500/纳指）
- mag7          七巨头
- star          明星股
- semiconductor 半导体重要股
- software      软件重要股

指数在 MySQL 中缺标准数据，需通过新浪美股指数日K免费接口补齐；
tag symbol 统一存 ^DJI / ^GSPC / ^IXIC，market='US'。
新浪 symbol：道指 .DJI / 标普500 .INX / 纳指 .IXIC。
"""

# (symbol, name, market, category)
TARGET_INSTRUMENTS: list[tuple[str, str, str, str]] = [
    # 美股三大指数（数据来自 yfinance/akshare）
    ('^DJI', '道琼斯工业指数', 'US', 'index'),
    ('^GSPC', '标普500指数', 'US', 'index'),
    ('^IXIC', '纳斯达克综合指数', 'US', 'index'),
    # 七巨头
    ('AAPL', '苹果', 'US', 'mag7'),
    ('MSFT', '微软', 'US', 'mag7'),
    ('GOOGL', '谷歌A', 'US', 'mag7'),
    ('AMZN', '亚马逊', 'US', 'mag7'),
    ('NVDA', '英伟达', 'US', 'mag7'),
    ('META', 'Meta', 'US', 'mag7'),
    ('TSLA', '特斯拉', 'US', 'mag7'),
    # 明星股
    ('NFLX', '奈飞', 'US', 'star'),
    ('AMD', '超威半导体', 'US', 'star'),
    ('INTC', '英特尔', 'US', 'star'),
    # 半导体重要股
    ('ASML', '阿斯麦', 'US', 'semiconductor'),
    ('AMAT', '应用材料', 'US', 'semiconductor'),
    ('TXN', '德州仪器', 'US', 'semiconductor'),
    ('LRCX', '泛林集团', 'US', 'semiconductor'),
    ('KLAC', '科磊', 'US', 'semiconductor'),
    ('MU', '美光科技', 'US', 'semiconductor'),
    ('QCOM', '高通', 'US', 'semiconductor'),
    ('AVGO', '博通', 'US', 'semiconductor'),
    # 软件重要股
    ('CRM', 'Salesforce', 'US', 'software'),
    ('ADBE', 'Adobe', 'US', 'software'),
    ('ORCL', '甲骨文', 'US', 'software'),
    ('NOW', 'ServiceNow', 'US', 'software'),
    ('SNOW', 'Snowflake', 'US', 'software'),
    ('PLTR', 'Palantir', 'US', 'software'),
    # 港股样本（列表/详情可用；日K视数据源覆盖）
    ('0700.HK', '腾讯控股', 'HK', 'star'),
    ('9988.HK', '阿里巴巴-SW', 'HK', 'star'),
    ('3690.HK', '美团-W', 'HK', 'star'),
    ('1810.HK', '小米集团-W', 'HK', 'star'),
    ('9618.HK', '京东集团-SW', 'HK', 'star'),
    # A股样本
    ('600519', '贵州茅台', 'CN', 'star'),
    ('000858', '五粮液', 'CN', 'star'),
    ('300750', '宁德时代', 'CN', 'semiconductor'),
    ('002594', '比亚迪', 'CN', 'star'),
    ('601318', '中国平安', 'CN', 'star'),
]

# 指数 symbol -> 新浪美股指数接口 symbol 映射
# 存库统一用标准符号 ^DJI/^GSPC/^IXIC，新浪源用 .DJI/.INX/.IXIC
INDEX_SOURCE_MAP: dict[str, dict[str, str]] = {
    '^DJI': {'sina': '.DJI'},
    '^GSPC': {'sina': '.INX'},
    '^IXIC': {'sina': '.IXIC'},
}

# 指数 symbol 集合（便于判断走免费源）
INDEX_SYMBOLS: set[str] = set(INDEX_SOURCE_MAP.keys())


def get_target_symbols() -> list[str]:
    """返回所有目标标的 symbol 列表。"""
    return [item[0] for item in TARGET_INSTRUMENTS]


def get_instrument_meta(symbol: str) -> tuple[str, str, str, str] | None:
    """按 symbol 返回目标标的元数据元组，找不到返回 None。"""
    for item in TARGET_INSTRUMENTS:
        if item[0] == symbol:
            return item
    return None
