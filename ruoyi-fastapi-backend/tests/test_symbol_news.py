"""标的绑定新闻：代码别名与标题匹配。"""

import os
import sys

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.symbol_news import payload_symbols, symbol_aliases, text_mentions_symbol


def test_symbol_aliases_us_hk_cn() -> None:
    assert 'AAPL' in symbol_aliases('AAPL', 'US')
    assert 'AAPL.US' in symbol_aliases('AAPL', 'US')
    aliases = symbol_aliases('00700', 'HK')
    assert '00700' in aliases
    assert '700' in aliases
    assert '700.HK' in aliases
    assert '600519.SH' in symbol_aliases('600519', 'CN')


def test_text_mentions_ticker_and_name() -> None:
    assert text_mentions_symbol('Apple beats estimates, AAPL jumps', 'AAPL', 'US', 'Apple')
    assert text_mentions_symbol('腾讯控股午后走强', '00700', 'HK', '腾讯控股')
    assert not text_mentions_symbol('Federal Reserve holds rates', 'AAPL', 'US', 'Apple')
    assert not text_mentions_symbol('AI chips rally', 'T', 'US', None)


def test_briefing_row_matches_symbol_payload() -> None:
    row = {
        'headline': '美股推荐关注 AAPL',
        'summary': '策略评分 80',
        'symbols': payload_symbols({'symbol': 'AAPL'}),
    }
    assert 'AAPL' in row['symbols']
    assert text_mentions_symbol(row['headline'], 'AAPL', 'US')


def test_payload_symbols() -> None:
    assert payload_symbols({'symbol': 'AAPL'}) == ['AAPL']
    assert payload_symbols({'symbols': ['MSFT', 'nvda']}) == ['MSFT', 'NVDA']
    assert payload_symbols(None) == []
