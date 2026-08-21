/**
 * v-hasPermi 操作权限处理
 */
import { usePermission } from '@/composables/usePermission'

export default {
  mounted(el, binding) {
    const { value } = binding
    const { hasPermi } = usePermission()
    if (value && value instanceof Array && value.length > 0) {
      if (!hasPermi(value)) {
        el.parentNode && el.parentNode.removeChild(el)
      }
    } else {
      throw new Error('请设置操作权限标签值')
    }
  }
}
