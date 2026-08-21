import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.watchlist_analyzer import WatchlistAiAnalyzer, rule_based_analysis


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


def test_parse_json_from_markdown() -> None:
    raw = '```json\n{"stance": "中性", "recommendation": "观望", "confidence": 51}\n```'
    parsed = WatchlistAiAnalyzer.parse_response(raw)
    assert parsed['stance'] == '中性'
    assert parsed['confidence'] == 51
