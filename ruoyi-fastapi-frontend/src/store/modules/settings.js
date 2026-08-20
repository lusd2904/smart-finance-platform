import defaultSettings from '@/settings'
import { useDark } from '@vueuse/core'
import { useDynamicTitle } from '@/utils/dynamicTitle'

const isDark = useDark({ initialValue: 'light' })

const { sideTheme, showSettings, navType, tagsView, tagsIcon, fixedHeader, sidebarLogo, dynamicTitle, footerVisible, footerContent } = defaultSettings

const storageSetting = JSON.parse(localStorage.getItem('layout-setting')) || ''

function themeKeyOf(dark) {
  return dark ? 'glass-dark' : 'glass-light'
}

function applyThemeToDocument(dark) {
  if (typeof document === 'undefined') {
    return
  }
  document.documentElement.setAttribute('data-theme', themeKeyOf(dark))
  document.documentElement.classList.toggle('dark', !!dark)
}

const useSettingsStore = defineStore(
  'settings',
  {
    state: () => ({
      title: '',
      theme: storageSetting.theme || '#6366F1',
      sideTheme: storageSetting.sideTheme || sideTheme,
      showSettings: showSettings,
      navType: storageSetting.navType === undefined ? navType : storageSetting.navType,
      tagsView: storageSetting.tagsView === undefined ? tagsView : storageSetting.tagsView,
      tagsIcon: storageSetting.tagsIcon === undefined ? tagsIcon : storageSetting.tagsIcon,
      fixedHeader: storageSetting.fixedHeader === undefined ? fixedHeader : storageSetting.fixedHeader,
      sidebarLogo: storageSetting.sidebarLogo === undefined ? sidebarLogo : storageSetting.sidebarLogo,
      dynamicTitle: storageSetting.dynamicTitle === undefined ? dynamicTitle : storageSetting.dynamicTitle,
      footerVisible: storageSetting.footerVisible === undefined ? footerVisible : storageSetting.footerVisible,
      footerContent: footerContent,
      isDark: isDark.value
    }),
    getters: {
      themeKey: (state) => themeKeyOf(state.isDark)
    },
    actions: {
      // 修改布局设置
      changeSetting(data) {
        const { key, value } = data
        if (this.hasOwnProperty(key)) {
          this[key] = value
        }
      },
      // 设置网页标题
      setTitle(title) {
        this.title = title
        useDynamicTitle()
      },
      // 把当前皮肤同步到 html.dark / data-theme（登录、门户、工作台共用）
      applyTheme() {
        this.isDark = !!isDark.value
        applyThemeToDocument(this.isDark)
      },
      // 显式选择浅色 / 深色，并写入 VueUse 同一持久化键
      setDark(dark) {
        const next = !!dark
        isDark.value = next
        this.isDark = next
        applyThemeToDocument(next)
      },
      // 切换暗黑模式
      toggleTheme() {
        this.setDark(!this.isDark)
      }
    }
  })

export default useSettingsStore

applyThemeToDocument(isDark.value)
