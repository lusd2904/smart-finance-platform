import { useUserStore } from '@/store/user'

/** Same contract as ruoyi v-hasPermi="['sentiment:news:collect']". */
export default {
  mounted(el, binding) {
    const value = binding.value
    const perms = Array.isArray(value) ? value : value ? [value] : []
    if (!perms.length) return
    const user = useUserStore()
    const ok = perms.some((perm) => user.hasPermi(perm))
    if (!ok) el.parentNode && el.parentNode.removeChild(el)
  }
}
