import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.watchlist_analyzer import WatchlistAiAnalyzer, rule_based_analysis
from module_market.service.watchlist_service import REC_SIGN, forward_returns_from_klines


def test_rule_based_bullish_ma() -> None:
    result = rule_based_analysis(
        {
            'price': 110,
            'changePercent': 1.2,
            'indicators': {'close': 110, 'ma': {'ma20': 100}, 'macd': {'macd': 0.4}, 'rsi': {'rsi12': 55}},
            'news': [{'title': 'n1'}],
            'sentimentNews': [],
        }
    )
    assert result['stance'] == '偏多'
    assert result['recommendation'] in {'持有', '买入', '加仓'}
    assert 30 <= result['confidence'] <= 80
    assert '资讯' in result['news_review']


def test_rule_based_overbought() -> None:
    result = rule_based_analysis(
        {
            'indicators': {'close': 120, 'ma': {'ma20': 100}, 'rsi': {'rsi12': 82}, 'macd': {'macd': 1}},
            'news': [],
            'sentimentNews': [{'title': 'x'}],
        }
    )
    assert result['recommendation'] == '减仓'


def test_forward_returns_from_analysis_date() -> None:
    klines = [
        {'date': '2024-06-03', 'close': 100},
        {'date': '2024-06-04', 'close': 110},
        {'date': '2024-06-05', 'close': 105},
        {'date': '2024-06-06', 'close': 108},
        {'date': '2024-06-07', 'close': 112},
        {'date': '2024-06-10', 'close': 120},
    ]
    out = forward_returns_from_klines(klines, '2024-06-03 15:00:00')
    assert out['fwd1'] == 10.0
    assert out['fwd5'] == 20.0
    pending = forward_returns_from_klines(klines, '2024-06-10')
    assert pending['fwd1'] is None
    assert pending['fwd5'] is None
    assert REC_SIGN['买入'] == 1
    assert REC_SIGN['卖出'] == -1


def test_parse_json_from_markdown() -> None:
    raw = '```json\n{"stance": "中性", "recommendation": "观望", "confidence": 51}\n```'
    parsed = WatchlistAiAnalyzer.parse_response(raw)
    assert parsed['stance'] == '中性'
    assert parsed['confidence'] == 51
