import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_client/core/api/api_result.dart';
import 'package:flutter_client/core/api/ruoyi_client.dart';
import 'package:flutter_client/core/menu/router_models.dart';

void main() {
  test('lustone 业务菜单不展示系统设置', () {
    const allowed = {
      '/market/heat',
      '/trade/terminal',
      '/quant/strategy',
      '/sentiment/dashboard',
      '/ai/chat',
    };
    expect(menuAllows(allowed, '/portal'), isTrue);
    expect(menuAllows(allowed, '/market/kline?symbol=AAPL'), isTrue);
    expect(menuAllows(allowed, '/trade/positions'), isTrue);
    expect(menuAllows(allowed, '/system/user'), isFalse);
    expect(menuAllows(allowed, '/monitor/job'), isFalse);
    expect(menuAllows(allowed, '/tool/swagger'), isFalse);
    expect(menuAllows(allowed, '/analysis/jobs'), isFalse);
    expect(menuAllows(const {}, '/monitor/job'), isFalse);
    expect(menuAllows(const {}, '/market/heat'), isTrue);
    expect(menuAllows(const {}, '/index'), isFalse);
    expect(menuAllows({'/system/user'}, '/system/user'), isFalse);
  });

  test('clientVisibleRouters 去掉系统管理树', () {
    final visible = clientVisibleRouters(const [
      RouterNode(
        path: '/market',
        meta: RouterMeta(title: '行情中心'),
        children: [RouterNode(path: 'heat', meta: RouterMeta(title: '市场热度'))],
      ),
      RouterNode(
        path: 'system',
        meta: RouterMeta(title: '系统管理'),
        children: [RouterNode(path: 'user', meta: RouterMeta(title: '用户管理'))],
      ),
      RouterNode(
        path: '/monitor',
        meta: RouterMeta(title: '系统监控'),
        children: [RouterNode(path: 'job', meta: RouterMeta(title: '定时任务'))],
      ),
    ]);
    expect(visible.map((n) => n.path), ['/market']);
    expect(isRestrictedMenuPath('/tool/gen'), isTrue);
    expect(isRestrictedMenuPath('/market/heat'), isFalse);
  });

  test('joinRoute 拼接父子路径', () {
    expect(joinRoute('/market', 'heat'), '/market/heat');
    expect(joinRoute('/market', '/heat'), '/heat');
    expect(joinRoute('', 'index'), '/index');
  });

  test('extractRows 兼容 rows / items / 数组', () {
    expect(
      extractRows(ApiResult.ok(rows: [
        {'a': 1},
      ])).length,
      1,
    );
    expect(
      extractRows(ApiResult.ok(data: {
        'items': [
          {'a': 1},
          {'a': 2},
        ],
      })).length,
      2,
    );
    expect(extractRows(ApiResult.ok(data: [{'a': 1}])).length, 1);
  });
}
