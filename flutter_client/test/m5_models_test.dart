import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/update/data/update_models.dart';

void main() {
  group('UpdateCheck', () {
    test('完整载荷解析与强更标记', () {
      final u = UpdateCheck.fromJson(const {
        'platform': 'android',
        'currentVersion': '1.0.0',
        'latestVersion': '1.2.0',
        'downloadUrl': 'https://example.com/app.apk',
        'notes': '修复若干问题',
        'updateAvailable': true,
        'forceUpdate': true,
      });
      expect(u.updateAvailable, isTrue);
      expect(u.forceUpdate, isTrue);
      expect(u.latestVersion, '1.2.0');
    });

    test('无发布平台：全空载荷按不更新处理', () {
      final u = UpdateCheck.fromJson(const {
        'platform': 'ios',
        'updateAvailable': false,
      });
      expect(u.updateAvailable, isFalse);
      expect(u.forceUpdate, isFalse);
      expect(u.downloadUrl, isEmpty);
    });

    test('服务端只给弱更标记时不升级为强更', () {
      final u = UpdateCheck.fromJson(const {
        'updateAvailable': true,
        'forceUpdate': false,
      });
      expect(u.updateAvailable, isTrue);
      expect(u.forceUpdate, isFalse);
    });
  });
}
