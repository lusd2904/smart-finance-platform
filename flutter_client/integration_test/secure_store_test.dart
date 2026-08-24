import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

/// macOS 沙箱下 flutter_secure_storage 需 keychain-access-groups 权限；
/// 缺失时 write 抛 errSecMissingEntitlement（读不存在的键不报错，故登录前无感）。
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('钥匙串写入→读取→删除（传统钥匙串）', (tester) async {
    // 传统钥匙串：不依赖签名 Team 前缀，ad-hoc/开发签均可用。
    // 数据保护钥匙串（默认）要求正式分发签名，留待 M5 发布工程切换。
    const storage = FlutterSecureStorage(
      mOptions: MacOsOptions(usesDataProtectionKeychain: false),
    );
    const key = 'smoke.keychain.v1';
    await storage.write(key: key, value: 'token-smoke');
    expect(await storage.read(key: key), 'token-smoke');
    await storage.delete(key: key);
    expect(await storage.read(key: key), isNull);
  });
}
