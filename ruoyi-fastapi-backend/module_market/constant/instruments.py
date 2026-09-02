"""
行情数据中心目标标的清单（常量）。

category 取值：
- index         美股三大指数（道指/标普500/纳指）
- mag7          七巨头
- star          明星股
- semiconductor 半导体重要股
- software      软件重要股
- listed        全市场代码（非精选池，默认列表接口不返回）

指数在 MySQL 中缺标准数据，需通过新浪美股指数日K免费接口补齐；
tag symbol 统一存 ^DJI / ^GSPC / ^IXIC，market='US'。
新浪 symbol：道指 .DJI / 标普500 .INX / 纳指 .IXIC。
"""

# 全市场代码入库分类；精选池（mag7/star/...）upsert 时不得被覆盖
LISTED_CATEGORY = 'listed'
LISTED_SEARCH_LIMIT = 200
UNIVERSE_PAGE_SIZE_DEFAULT = 50
UNIVERSE_PAGE_SIZE_MAX = 200


def sanitize_instrument_keyword(keyword: str | None) -> str:
    """去掉通配符后截断，避免 LIKE 注入式膨胀。"""
    return (keyword or '').strip().replace('%', '').replace('_', '')[:32]


def featured_list_excludes_listed(category: str | None, keyword: str | None) -> bool:
    """精选列表无分类、无关键字时排除 listed，避免一次打出全市场。"""
    return not (category or '').strip() and not sanitize_instrument_keyword(keyword)


def build_quotes_from_ranked_bars(rows: list[object]) -> dict[str, dict[str, object]]:
    """把每个 symbol 最近两根日K（rn=1 最新）收成最新价与涨跌幅。"""
    latest: dict[str, dict[str, object]] = {}
    prev_close: dict[str, float] = {}
    for row in rows:
        symbol = getattr(row, 'symbol', None)
        if not symbol:
            continue
        rn = int(getattr(row, 'rn', 0) or 0)
        close = getattr(row, 'close_price', None)
        if rn == 1:
            latest[symbol] = {
                'price': close,
                'tradeDate': getattr(row, 'trade_date', None),
                'volume': getattr(row, 'volume', None),
            }
        elif rn == 2 and close is not None:
            prev_close[symbol] = float(close)
    for symbol, item in latest.items():
        price = item.get('price')
        prev = prev_close.get(symbol)
        item['prevClose'] = prev
        change_rate = None
        if price is not None and prev not in (None, 0):
            change_rate = (float(price) - float(prev)) / float(prev) * 100
        item['changeRate'] = change_rate
        item['up'] = None if change_rate is None else change_rate >= 0
    return latest


def clamp_universe_page(page_num: int | None, page_size: int | None) -> tuple[int, int]:
    """全市场列表强制分页：页码从 1 起，每页最多 200。"""
    try:
        pn = int(page_num or 1)
    except (TypeError, ValueError):
        pn = 1
    try:
        ps = int(page_size or UNIVERSE_PAGE_SIZE_DEFAULT)
    except (TypeError, ValueError):
        ps = UNIVERSE_PAGE_SIZE_DEFAULT
    pn = max(pn, 1)
    if ps < 1:
        ps = UNIVERSE_PAGE_SIZE_DEFAULT
    ps = min(ps, UNIVERSE_PAGE_SIZE_MAX)
    return pn, ps

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
    # 美股宽基 / 金融消费医疗
    ('SPY', '标普500ETF', 'US', 'etf'),
    ('QQQ', '纳指100ETF', 'US', 'etf'),
    ('DIA', '道指ETF', 'US', 'etf'),
    ('IWM', '罗素2000ETF', 'US', 'etf'),
    ('JPM', '摩根大通', 'US', 'finance'),
    ('BAC', '美国银行', 'US', 'finance'),
    ('WFC', '富国银行', 'US', 'finance'),
    ('V', 'Visa', 'US', 'finance'),
    ('MA', '万事达', 'US', 'finance'),
    ('JNJ', '强生', 'US', 'healthcare'),
    ('UNH', '联合健康', 'US', 'healthcare'),
    ('LLY', '礼来', 'US', 'healthcare'),
    ('ABBV', '艾伯维', 'US', 'healthcare'),
    ('MRK', '默沙东', 'US', 'healthcare'),
    ('PFE', '辉瑞', 'US', 'healthcare'),
    ('XOM', '埃克森美孚', 'US', 'energy'),
    ('CVX', '雪佛龙', 'US', 'energy'),
    ('WMT', '沃尔玛', 'US', 'consumer'),
    ('PG', '宝洁', 'US', 'consumer'),
    ('KO', '可口可乐', 'US', 'consumer'),
    ('PEP', '百事', 'US', 'consumer'),
    ('COST', '开市客', 'US', 'consumer'),
    ('MCD', '麦当劳', 'US', 'consumer'),
    ('HD', '家得宝', 'US', 'consumer'),
    ('DIS', '迪士尼', 'US', 'star'),
    ('UBER', 'Uber', 'US', 'star'),
    ('CSCO', '思科', 'US', 'software'),
    ('IBM', 'IBM', 'US', 'software'),
    ('GE', '通用电气', 'US', 'industrial'),
    ('CAT', '卡特彼勒', 'US', 'industrial'),
    ('BA', '波音', 'US', 'industrial'),
    ('HON', '霍尼韦尔', 'US', 'industrial'),
    # 港股
    ('0700.HK', '腾讯控股', 'HK', 'star'),
    ('9988.HK', '阿里巴巴-SW', 'HK', 'star'),
    ('3690.HK', '美团-W', 'HK', 'star'),
    ('1810.HK', '小米集团-W', 'HK', 'star'),
    ('9618.HK', '京东集团-SW', 'HK', 'star'),
    ('0005.HK', '汇丰控股', 'HK', 'finance'),
    ('0939.HK', '建设银行', 'HK', 'finance'),
    ('1398.HK', '工商银行', 'HK', 'finance'),
    ('3988.HK', '中国银行', 'HK', 'finance'),
    ('1299.HK', '友邦保险', 'HK', 'finance'),
    ('0388.HK', '香港交易所', 'HK', 'finance'),
    ('2318.HK', '中国平安', 'HK', 'finance'),
    ('1211.HK', '比亚迪股份', 'HK', 'star'),
    ('2020.HK', '安踏体育', 'HK', 'consumer'),
    ('2269.HK', '药明生物', 'HK', 'healthcare'),
    # A股
    ('600519', '贵州茅台', 'CN', 'star'),
    ('000858', '五粮液', 'CN', 'star'),
    ('300750', '宁德时代', 'CN', 'semiconductor'),
    ('002594', '比亚迪', 'CN', 'star'),
    ('601318', '中国平安', 'CN', 'finance'),
    ('600036', '招商银行', 'CN', 'finance'),
    ('601166', '兴业银行', 'CN', 'finance'),
    ('000001', '平安银行', 'CN', 'finance'),
    ('601398', '工商银行', 'CN', 'finance'),
    ('000333', '美的集团', 'CN', 'consumer'),
    ('002415', '海康威视', 'CN', 'star'),
    ('600276', '恒瑞医药', 'CN', 'healthcare'),
    ('601888', '中国中免', 'CN', 'consumer'),
    ('600900', '长江电力', 'CN', 'energy'),
    ('601899', '紫金矿业', 'CN', 'energy'),
    ('002475', '立讯精密', 'CN', 'semiconductor'),
    ('300059', '东方财富', 'CN', 'finance'),
    ('601012', '隆基绿能', 'CN', 'energy'),
    ('TSM', '台积电', 'US', 'semiconductor'),
    ('LIN', '林德', 'US', 'industrial'),
    ('ACN', '埃森哲', 'US', 'software'),
    ('ABT', '雅培', 'US', 'healthcare'),
    ('NEE', 'NextEra Energy', 'US', 'energy'),
    ('PM', '菲利普莫里斯', 'US', 'consumer'),
    ('RTX', 'RTX', 'US', 'industrial'),
    ('AMGN', '安进', 'US', 'healthcare'),
    ('TMO', '赛默飞', 'US', 'healthcare'),
    ('UNP', '联合太平洋', 'US', 'industrial'),
    ('LOW', '劳氏', 'US', 'consumer'),
    ('INTU', 'Intuit', 'US', 'software'),
    ('GS', '高盛', 'US', 'finance'),
    ('MS', '摩根士丹利', 'US', 'finance'),
    ('BLK', '贝莱德', 'US', 'finance'),
    ('AXP', '美国运通', 'US', 'finance'),
    ('BKNG', 'Booking', 'US', 'consumer'),
    ('SBUX', '星巴克', 'US', 'consumer'),
    ('NKE', '耐克', 'US', 'consumer'),
    ('CMCSA', '康卡斯特', 'US', 'star'),
    ('0941.HK', '中国移动', 'HK', 'star'),
    ('0001.HK', '长和', 'HK', 'industrial'),
    ('0016.HK', '新鸿基地产', 'HK', 'finance'),
    ('0027.HK', '银河娱乐', 'HK', 'consumer'),
    ('0175.HK', '吉利汽车', 'HK', 'star'),
    ('2382.HK', '舜宇光学', 'HK', 'semiconductor'),
    ('1024.HK', '快手-W', 'HK', 'star'),
    ('2015.HK', '理想汽车', 'HK', 'star'),
    ('600000', '浦发银行', 'CN', 'finance'),
    ('601288', '农业银行', 'CN', 'finance'),
    ('000651', '格力电器', 'CN', 'consumer'),
    ('002304', '洋河股份', 'CN', 'star'),
    ('300760', '迈瑞医疗', 'CN', 'healthcare'),
    ('688981', '中芯国际', 'CN', 'semiconductor'),
    ('600030', '中信证券', 'CN', 'finance'),
    ('000725', '京东方A', 'CN', 'star'),
    ('002371', '北方华创', 'CN', 'semiconductor'),
    ('603259', '药明康德', 'CN', 'healthcare'),
    ('300274', '阳光电源', 'CN', 'energy'),
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
