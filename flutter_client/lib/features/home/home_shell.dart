import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../shell/admin_shell.dart';
import '../shell/desktop_web_shell.dart';

/// 登录后的主界面。
/// 宽屏（macOS/Windows）直接打开网关 Web 控制台，页面与 Docker Web 一致；
/// 手机继续走原生五栏。
class HomeShell extends StatelessWidget {
  const HomeShell({super.key});

  @override
  Widget build(BuildContext context) {
    if (AppDimens.isWide(context)) {
      return const DesktopWebShell();
    }
    return const AdminShell();
  }
}
