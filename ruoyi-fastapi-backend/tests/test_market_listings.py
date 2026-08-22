import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.constant.instruments import LISTED_CATEGORY
from module_market.service.listing_service import (
    _paginate,
    dedupe_instruments,
    listed_category_after_upsert,
    normalize_cn_symbol,
    normalize_hk_symbol,
    normalize_us_symbol,
    parse_eastmoney_diff,
    parse_nasdaq_listed,
    parse_nasdaq_otherlisted,
    parse_sina_cn_rows,
    parse_sina_hk_rows,
    parse_sina_us_jsonp,
)


def test_normalize_symbols() -> None:
    assert normalize_cn_symbol('sh600519') == '600519'
    assert normalize_cn_symbol('000001') == '000001'
    assert normalize_cn_symbol('bj920000') == '920000'
    assert normalize_cn_symbol('AAPL') is None
    assert normalize_hk_symbol('00001') == '0001.HK'
    assert normalize_hk_symbol('00700') == '0700.HK'
    assert normalize_hk_symbol('0700.HK') == '0700.HK'
    assert normalize_hk_symbol('9988') == '9988.HK'
    assert normalize_hk_symbol('40001') is None
    assert normalize_hk_symbol('89988') is None
    assert normalize_us_symbol('aapl') == 'AAPL'
    assert normalize_us_symbol('BRK.A') == 'BRK.A'
    assert normalize_us_symbol('AAPL.US') == 'AAPL'
    assert normalize_us_symbol('^DJI') is None
    assert normalize_us_symbol('BRK A') is None


def test_listed_category_preserves_featured() -> None:
    assert listed_category_after_upsert(None) == LISTED_CATEGORY
    assert listed_category_after_upsert('') == LISTED_CATEGORY
    assert listed_category_after_upsert('listed') == LISTED_CATEGORY
    assert listed_category_after_upsert('mag7') == 'mag7'
    assert listed_category_after_upsert('star') == 'star'
    assert listed_category_after_upsert('index') == 'index'


def test_parse_sina_and_eastmoney_payloads() -> None:
    cn = parse_sina_cn_rows(
        [
            {'symbol': 'sh600519', 'code': '600519', 'name': '贵州茅台'},
            {'symbol': 'sz000001', 'code': '000001', 'name': '平安银行'},
            {'symbol': 'bad', 'code': 'X', 'name': 'skip'},
        ]
    )
    assert [r['symbol'] for r in cn] == ['600519', '000001']
    assert cn[0]['market'] == 'CN'
    assert cn[0]['category'] == LISTED_CATEGORY

    hk = parse_sina_hk_rows([{'symbol': '00700', 'name': '腾讯控股', 'engname': 'TENCENT'}])
    assert hk[0]['symbol'] == '0700.HK'
    assert hk[0]['name'] == '腾讯控股'

    total, us = parse_sina_us_jsonp(
        'var t=({"count":"2","data":[{"symbol":"AAPL","name":"Apple","cname":"苹果","market":"NASDAQ"},'
        '{"symbol":"^DJI","name":"Dow","cname":"道指"}]});'
    )
    assert total == 2
    assert [r['symbol'] for r in us] == ['AAPL']
    assert us[0]['name'] == '苹果'

    em = parse_eastmoney_diff([{'f12': '600519', 'f14': '贵州茅台'}, {'f12': '00700', 'f14': '腾讯'}], 'CN')
    assert em[0]['symbol'] == '600519'
    hk_em = parse_eastmoney_diff([{'f12': '00700', 'f14': '腾讯控股'}], 'HK')
    assert hk_em[0]['symbol'] == '0700.HK'


def test_parse_nasdaq_files() -> None:
    listed = parse_nasdaq_listed(
        'Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\r\n'
        'AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\r\n'
        'SPY|SPDR S&P 500 ETF Trust|G|N|N|100|Y|N\r\n'
        'ZZZZ|Test Issue|G|Y|N|100|N|N\r\n'
        'File Creation Time: 080120261234\r\n'
    )
    assert [r['symbol'] for r in listed] == ['AAPL']
    other = parse_nasdaq_otherlisted(
        'ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\r\n'
        'IBM|International Business Machines|N|IBM|N|100|N|IBM\r\n'
        'GLD|SPDR Gold Trust|P|GLD|Y|100|N|GLD\r\n'
        'ZZZ|Test|N|ZZZ|N|100|Y|ZZZ\r\n'
    )
    assert [r['symbol'] for r in other] == ['IBM']


def test_skip_hk_warrants_and_us_etf_payloads() -> None:
    hk = parse_sina_hk_rows(
        [
            {'symbol': '00700', 'name': '腾讯控股'},
            {'symbol': '89988', 'name': '阿里巴巴-WR'},
            {'symbol': '80700', 'name': '腾讯控股-R'},
        ]
    )
    assert [r['symbol'] for r in hk] == ['0700.HK']
    em = parse_eastmoney_diff(
        [{'f12': '00700', 'f14': '腾讯控股'}, {'f12': '89988', 'f14': '阿里巴巴-WR'}],
        'HK',
    )
    assert [r['symbol'] for r in em] == ['0700.HK']
    total, us = parse_sina_us_jsonp(
        'var t=({"count":"2","data":[{"symbol":"AAPL","name":"Apple Inc Common Stock","cname":"苹果"},'
        '{"symbol":"SPY","name":"SPDR S&P 500 ETF Trust","cname":"SPDR标普500ETF"}]});'
    )
    assert total == 2
    assert [r['symbol'] for r in us] == ['AAPL']


def test_paginate_uses_raw_count_not_filtered_len() -> None:
    pages = {
        1: ([{'symbol': 'A'}], 60),
        2: ([{'symbol': 'B'}], 60),
        3: ([{'symbol': 'C'}], 10),
        4: ([], 0),
    }

    def fetch_page(pn: int) -> tuple[list[dict[str, str]], int]:
        return pages.get(pn, ([], 0))

    out = _paginate(fetch_page, page_size=80)
    assert [r['symbol'] for r in out] == ['A', 'B', 'C']


def test_dedupe_keeps_first() -> None:
    rows = [
        {'symbol': 'AAPL', 'name': '苹果', 'market': 'US', 'category': LISTED_CATEGORY},
        {'symbol': 'AAPL', 'name': 'Apple', 'market': 'US', 'category': LISTED_CATEGORY},
        {'symbol': 'MSFT', 'name': '微软', 'market': 'US', 'category': LISTED_CATEGORY},
    ]
    out = dedupe_instruments(rows)
    assert [r['symbol'] for r in out] == ['AAPL', 'MSFT']
    assert out[0]['name'] == '苹果'
