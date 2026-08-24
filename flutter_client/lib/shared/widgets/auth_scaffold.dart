import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import 'brand_logo.dart';

/// 认证 / 引导页统一骨架：
/// - 宽屏（≥900）：左侧品牌面板 + 右侧表单区；
/// - 窄屏：顶部字标 + 居中单栏表单。
/// 登录、注册、网关配置共用，保证首启链路视觉一致。
class AuthScaffold extends StatelessWidget {
  const AuthScaffold({
    super.key,
    required this.child,
    required this.title,
    this.subtitle,
    this.headerActions,
  });

  /// 表单内容（不含页头）。
  final Widget child;
  final String title;
  final String? subtitle;

  /// 页头右侧动作（如「网关设置」入口）。
  final List<Widget>? headerActions;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= AppDimens.wideBreakpoint;
    final form = ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 420),
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 32),
        shrinkWrap: true,
        children: [
          if (!wide) ...[
            const BrandWordmark(markSize: 40),
            const SizedBox(height: 28),
          ],
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: _titleStyle(context)),
                    if (subtitle != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        subtitle!,
                        style: TextStyle(
                          fontSize: 13.5,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              ...?headerActions,
            ],
          ),
          const SizedBox(height: 24),
          child,
        ],
      ),
    );

    if (!wide) {
      return Scaffold(
        body: SafeArea(
          child: Center(child: SingleChildScrollView(child: form)),
        ),
      );
    }
    return Scaffold(
      body: Row(
        children: [
          const SizedBox(width: 420, child: _BrandPanel()),
          const VerticalDivider(width: 1),
          Expanded(
            child: Center(child: SingleChildScrollView(child: form)),
          ),
        ],
      ),
    );
  }

  TextStyle _titleStyle(BuildContext context) => TextStyle(
    fontSize: 22,
    height: 1.25,
    fontWeight: FontWeight.w800,
    color: Theme.of(context).colorScheme.onSurface,
  );
}

/// 品牌面板：深蓝渐变 + 功能关键词。仅静态品牌内容，不承载交互。
class _BrandPanel extends StatelessWidget {
  const _BrandPanel();

  static const _keywords = ['行情', '舆情', '量化', '交易'];

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0A1120), Color(0xFF13233E)],
        ),
      ),
      padding: const EdgeInsets.all(40),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const BrandMark(size: 46),
          const Spacer(),
          const Text(
            '智慧金融终端',
            style: TextStyle(
              color: Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.w800,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            '行情 · 舆情 · 量化 · 交易\n一站式投研工作台，四端同步。',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.72),
              fontSize: 14,
              height: 1.6,
            ),
          ),
          const SizedBox(height: 24),
          Wrap(
            spacing: 8,
            children: [
              for (final k in _keywords)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 5,
                  ),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: Colors.white24),
                  ),
                  child: Text(
                    k,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.85),
                      fontSize: 12,
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

/// 表单错误行：图标 + 文案，登录/注册/网关共用。
class FormErrorText extends StatelessWidget {
  const FormErrorText(this.message, {super.key});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.error_outline_rounded, size: 16, color: scheme.error),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            message,
            style: TextStyle(fontSize: 13, color: scheme.error),
          ),
        ),
      ],
    );
  }
}
