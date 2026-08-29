"""把长桥 QuoteContext.subscribe 接到现有行情 WS。

多个 WS 连接的标的取并集，进程内一份 QuoteContext；推送写入内存，
LiveQuotesService / WS 轮询读这份最新价，腾讯仍补缺口。SDK 不可用时静默降级。
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable
from typing import Any

from utils.log_util import logger

OnUpdate = Callable[[], None]


class QuoteSubscribeHub:
    _lock = threading.RLock()
    _watchers: dict[str, list[tuple[str, str]]] = {}
    _callbacks: dict[str, OnUpdate] = {}
    _latest: dict[tuple[str, str], dict[str, Any]] = {}
    _subscribed: set[str] = set()
    _handler_bound = False

    @classmethod
    def latest_for(cls, pairs: list[tuple[str, str]]) -> list[dict[str, Any]]:
        if not pairs:
            return []
        with cls._lock:
            return [cls._latest[pair] for pair in pairs if pair in cls._latest]

    @classmethod
    def subscribed_count(cls) -> int:
        with cls._lock:
            return len(cls._subscribed)

    @classmethod
    async def watch(
        cls,
        watcher_id: str,
        pairs: list[tuple[str, str]],
        on_update: OnUpdate | None = None,
    ) -> None:
        watcher_id = str(watcher_id or '')
        if not watcher_id:
            return
        from module_market.service.live_quotes_service import parse_subscribe_symbols

        normalized = parse_subscribe_symbols([{'symbol': symbol, 'market': market} for symbol, market in pairs])
        with cls._lock:
            if normalized:
                cls._watchers[watcher_id] = normalized
                if on_update is not None:
                    cls._callbacks[watcher_id] = on_update
            else:
                cls._watchers.pop(watcher_id, None)
                cls._callbacks.pop(watcher_id, None)
        try:
            await asyncio.to_thread(cls._sync_subscriptions)
        except Exception as exc:
            logger.info(f'[行情订阅] 同步跳过: {exc}')

    @classmethod
    async def unwatch(cls, watcher_id: str) -> None:
        await cls.watch(watcher_id, [])

    @classmethod
    def ingest_push(cls, symbol: str, quote: Any) -> dict[str, Any] | None:
        """测试与 SDK 回调共用：把 PushQuote 写成内部最新价。"""
        item = map_push_quote(symbol, quote)
        if item is None:
            return None
        pair = (item['symbol'], item['market'])
        with cls._lock:
            previous = cls._latest.get(pair)
            if previous and item.get('prevClose') is None:
                item['prevClose'] = previous.get('prevClose')
                last = item.get('last')
                prev = item.get('prevClose')
                if last and prev:
                    try:
                        item['changePct'] = round((float(last) / float(prev) - 1.0) * 100, 2)
                        item['changeRate'] = item['changePct']
                    except (TypeError, ValueError, ZeroDivisionError):
                        pass
            cls._latest[pair] = item
            callbacks = list(cls._callbacks.values())
        for callback in callbacks:
            with contextlib.suppress(Exception):
                callback()
        return item

    @classmethod
    def reset_for_tests(cls) -> None:
        with cls._lock:
            cls._watchers.clear()
            cls._callbacks.clear()
            cls._latest.clear()
            cls._subscribed.clear()
            cls._handler_bound = False

    @classmethod
    def _desired_lb_symbols(cls) -> list[str]:
        from module_market.service.live_quotes_service import MAX_LIVE_SYMBOLS, _longbridge_symbol_map

        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        with cls._lock:
            watchers = list(cls._watchers.values())
        for group in watchers:
            for pair in group:
                if pair in seen:
                    continue
                seen.add(pair)
                pairs.append(pair)
                if len(pairs) >= MAX_LIVE_SYMBOLS:
                    break
            if len(pairs) >= MAX_LIVE_SYMBOLS:
                break
        lb_symbols, _by_lb = _longbridge_symbol_map(pairs)
        return lb_symbols

    @classmethod
    def _sync_subscriptions(cls) -> None:
        from module_quant.service.longbridge_service import LongbridgeService

        try:
            if not LongbridgeService.is_configured() or LongbridgeService._blocked():
                return
        except Exception:
            return
        desired = set(cls._desired_lb_symbols())
        with cls._lock:
            current = set(cls._subscribed)
        to_add = [symbol for symbol in desired if symbol not in current]
        to_drop = [symbol for symbol in current if symbol not in desired]
        if not to_add and not to_drop:
            return
        if to_add:
            bound = cls._bind_handler()
            result = LongbridgeService.subscribe_quotes(to_add)
            if result.get('ok'):
                cls._seed_snapshot(to_add)
                with cls._lock:
                    cls._subscribed.update(to_add)
                    if bound:
                        cls._handler_bound = True
            else:
                logger.info(f'[行情订阅] 长桥 subscribe 跳过: {result.get("message")}')
        if to_drop:
            LongbridgeService.unsubscribe_quotes(to_drop)
            with cls._lock:
                cls._subscribed.difference_update(to_drop)
                drop_pairs = [pair for pair, item in cls._latest.items() if cls._lb_symbol_of(item) in set(to_drop)]
                for pair in drop_pairs:
                    cls._latest.pop(pair, None)

    @classmethod
    def _bind_handler(cls) -> bool:
        from module_quant.service.longbridge_service import LongbridgeService

        with cls._lock:
            if cls._handler_bound:
                return False
        result = LongbridgeService.set_quote_handler(cls._on_sdk_quote)
        return bool(result.get('ok'))

    @classmethod
    def _on_sdk_quote(cls, *args: Any) -> None:
        symbol = ''
        quote: Any = None
        if len(args) >= 2:  # noqa: PLR2004 - SDK 回调 (symbol, PushQuote)
            symbol, quote = args[0], args[1]
        elif len(args) == 1:
            quote = args[0]
            symbol = getattr(quote, 'symbol', '') or ''
        else:
            return
        try:
            cls.ingest_push(str(symbol or ''), quote)
        except Exception as exc:
            logger.info(f'[行情订阅] 推送处理跳过: {exc}')

    @classmethod
    def _seed_snapshot(cls, lb_symbols: list[str]) -> None:
        from module_market.service.live_quotes_service import _items_from_longbridge_quotes, _longbridge_symbol_map
        from module_quant.service.longbridge_service import LongbridgeService

        if not lb_symbols:
            return
        try:
            result = LongbridgeService.get_realtime_quote(lb_symbols) or {}
        except Exception as exc:
            logger.info(f'[行情订阅] 快照种子失败: {exc}')
            return
        _lb_symbols, by_lb = _longbridge_symbol_map(_pairs_from_lb(lb_symbols))
        del _lb_symbols
        items = _items_from_longbridge_quotes(result.get('quotes') or [], by_lb)
        with cls._lock:
            for item in items:
                pair = (item['symbol'], item['market'])
                cls._latest.setdefault(pair, item)

    @staticmethod
    def _lb_symbol_of(item: dict[str, Any]) -> str:
        from module_quant.service.longbridge_service import LongbridgeService

        try:
            return str(LongbridgeService.to_longbridge_symbol(item.get('symbol'), item.get('market')) or '')
        except Exception:
            return ''


def _pairs_from_lb(lb_symbols: list[str]) -> list[tuple[str, str]]:
    from module_market.service.live_quotes_service import normalize_symbol_market

    pairs: list[tuple[str, str]] = []
    for raw in lb_symbols:
        normalized = normalize_symbol_market(raw)
        if normalized:
            pairs.append(normalized)
    return pairs


def map_push_quote(symbol: str, quote: Any) -> dict[str, Any] | None:
    from module_market.service.live_quotes_service import _quote_item, normalize_symbol_market
    from module_quant.service.longbridge_quote import fmt_ts, to_float

    lb_symbol = str(symbol or getattr(quote, 'symbol', '') or '').strip()
    pair = normalize_symbol_market(lb_symbol)
    if pair is None:
        return None
    last = to_float(_attr(quote, 'last_done', 'lastDone', 'last'))
    if last is None:
        return None
    prev = to_float(_attr(quote, 'prev_close', 'prevClose'))
    quote_time = fmt_ts(_attr(quote, 'timestamp', 'quoteTime'), with_time=True)
    name = _attr(quote, 'name') or pair[0]
    return _quote_item(
        pair[0],
        pair[1],
        last=last,
        prev=prev,
        change_pct=None,
        quote_time=quote_time,
        name=name,
        source='longbridge',
    )


def _attr(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name] is not None:
                return obj[name]
        return None
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return None
