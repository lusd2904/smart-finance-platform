export default {
  /**
   * 网页标题
   */
  title: import.meta.env.VITE_APP_TITLE,

  /**
   * 侧边栏主题 深色主题theme-dark，浅色主题theme-light
   * 默认与原版 RuoYi 一致使用深色侧栏；可在布局设置中切换浅色
   */
  sideTheme: 'theme-dark',

  /**
   * 是否系统布局配置
   */
  showSettings: true,

  /**
   * 菜单导航模式 1、纯左侧 2、混合（左侧+顶部） 3、纯顶部
   */
  navType: 1,

  /**
   * 是否显示 tagsView（多页签导航）
   */
  tagsView: true,

  /**
   * 显示页签图标
   */
  tagsIcon: true,

  /**
   * 是否固定头部
   */
  fixedHeader: true,

  /**
   * 是否显示logo
   */
  sidebarLogo: true,

  /**
   * 是否显示动态标题
   */
  dynamicTitle: true,

  /**
   * 是否显示底部版权
   */
  footerVisible: false,

  /**
   * 底部版权文本内容
   */
  footerContent: 'Copyright © 2024-2026 insistence.tech All Rights Reserved.'
}
