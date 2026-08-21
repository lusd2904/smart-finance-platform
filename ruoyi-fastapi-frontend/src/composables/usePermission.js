import { computed } from 'vue'
import auth from '@/plugins/auth'
import useUserStore from '@/store/modules/user'

export function usePermission() {
  const userStore = useUserStore()
  const permissions = computed(() => userStore.permissions || [])
  const roles = computed(() => userStore.roles || [])

  function hasPermi(value) {
    if (Array.isArray(value)) return auth.hasPermiOr(value)
    return auth.hasPermi(value)
  }

  function hasRole(value) {
    if (Array.isArray(value)) return auth.hasRoleOr(value)
    return auth.hasRole(value)
  }

  return { hasPermi, hasRole, permissions, roles }
}
