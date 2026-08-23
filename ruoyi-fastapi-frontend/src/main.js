import { createApp } from 'vue'

import Cookies from 'js-cookie'

import { ElLoading, provideGlobalConfig } from 'element-plus'
import locale from 'element-plus/es/locale/lang/zh-cn'

// 深色模式变量
import 'element-plus/theme-chalk/dark/css-vars.css'
// 程序式 API（$modal、请求错误提示等在 js 中显式 import 调用）的组件样式：
// 显式 import 场景 resolver 不会注入样式，这里统一全局引入，保证 ElMessage/ElMessageBox/ElNotification/ElLoading.service 样式可用
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/notification/style/css'
import 'element-plus/es/components/loading/style/css'

import '@/assets/styles/index.scss' // global css

import App from './App'
import store from './store'
import router from './router'
import directive from './directive' // directive

// 注册指令
import plugins from './plugins' // plugins
import { download } from '@/utils/request'

// svg图标
import 'virtual:svg-icons-register'
import SvgIcon from '@/components/SvgIcon'
import elementIcons from '@/components/SvgIcon/svgicon'

import './permission' // permission control

import { useDict } from '@/utils/dict'
import { getConfigKey } from "@/api/system/config"
import { parseTime, resetForm, addDateRange, handleTree, selectDictLabel, selectDictLabels } from '@/utils/ruoyi'

// 分页组件
import Pagination from '@/components/Pagination'
// 自定义表格工具组件
import RightToolbar from '@/components/RightToolbar'
// 富文本组件
import Editor from "@/components/Editor"
// 文件上传组件
import FileUpload from "@/components/FileUpload"
// 图片上传组件
import ImageUpload from "@/components/ImageUpload"
// 图片预览组件
import ImagePreview from "@/components/ImagePreview"
// 字典标签组件
import DictTag from '@/components/DictTag'
import MarketIndexStrip from '@/components/MarketIndexStrip'

const app = createApp(App)

// 全局方法挂载
app.config.globalProperties.useDict = useDict
app.config.globalProperties.download = download
app.config.globalProperties.parseTime = parseTime
app.config.globalProperties.resetForm = resetForm
app.config.globalProperties.handleTree = handleTree
app.config.globalProperties.addDateRange = addDateRange
app.config.globalProperties.getConfigKey = getConfigKey
app.config.globalProperties.selectDictLabel = selectDictLabel
app.config.globalProperties.selectDictLabels = selectDictLabels

// 全局组件挂载
app.component('DictTag', DictTag)
app.component('MarketIndexStrip', MarketIndexStrip)
app.component('Pagination', Pagination)
app.component('FileUpload', FileUpload)
app.component('ImageUpload', ImageUpload)
app.component('ImagePreview', ImagePreview)
app.component('RightToolbar', RightToolbar)
app.component('Editor', Editor)

app.use(router)
app.use(store)
app.use(plugins)
app.use(elementIcons)
app.component('svg-icon', SvgIcon)

directive(app)

// Element Plus 按需引入（vite.config.js 中由 unplugin resolver 处理模板组件）：
// 这里仅保留必要的全局件——zh-cn 语言包与 size 全局配置、v-loading 指令
provideGlobalConfig({
  locale: locale,
  // 支持 large、default、small
  size: Cookies.get('size') || 'default'
}, app, true)

// v-loading 指令全局使用，需显式注册
app.use(ElLoading)

app.mount('#app')
