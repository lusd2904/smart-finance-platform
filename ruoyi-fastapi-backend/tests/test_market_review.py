import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.market_review_analyzer import rule_based_market_review
from module_market.service.watchlist_analyzer import WatchlistAiAnalyzer


def test_rule_based_review_bullish() -> None:
    result = rule_based_market_review(
        {
            'market': 'US',
            'marketLabel': '美股',
            'tradeDate': '2026-08-20',
            'benchmarks': [
                {'name': '标普500', 'changeRate': 1.2, 'changeText': '+1.20%'},
                {'name': '纳指', 'changeRate': 1.6, 'changeText': '+1.60%'},
            ],
            'upCount': 18,
            'downCount': 4,
            'sampleCount': 22,
            'news': [{'headline': 'n1'}],
            'sentiment': [],
        }
    )
    assert result['stance'] == '偏多'
    assert 50 < result['score'] <= 100
    assert '美股' in result['title']


def test_rule_based_review_bearish() -> None:
    result = rule_based_market_review(
        {
            'marketLabel': 'A股',
            'tradeDate': '2026-08-21',
            'benchmarks': [{'name': '茅台', 'changeRate': -1.4, 'changeText': '-1.40%'}],
            'upCount': 3,
            'downCount': 16,
            'sampleCount': 19,
            'news': [],
            'sentiment': [],
        }
    )
    assert result['stance'] == '偏空'
    assert result['score'] < 50
    assert result['news_review'] == '暂无有效资讯'


def test_parse_market_review_json() -> None:
    raw = '{"title": "美股反弹", "stance": "偏多", "score": 66, "summary": "ok"}'
    parsed = WatchlistAiAnalyzer.parse_response(raw)
    assert parsed['stance'] == '偏多'
    assert parsed['score'] == 66
