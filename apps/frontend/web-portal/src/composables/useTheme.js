import { computed, ref } from 'vue'

const STORAGE_KEY = 'sfp-active-theme'

const themeOptions = [
  {
    id: 'glass-dark',
    mode: 'dark',
    label: '幻彩琉璃 (深色)',
    description: '深邃高透的暗色毛玻璃质感，顶级金融终端体验',
    preview: '#08101d'
  },
  {
    id: 'glass-light',
    mode: 'light',
    label: '晨曦白玉 (浅色)',
    description: '极简通透的浅色毛玻璃，适合日间长时盯盘',
    preview: '#f8f9fc'
  }
]

const isValidTheme = (themeId) => themeOptions.some((theme) => theme.id === themeId)

const resolveTheme = () => {
  if (typeof window === 'undefined') return themeOptions[0].id
  const storedTheme = window.localStorage.getItem(STORAGE_KEY)
  return isValidTheme(storedTheme) ? storedTheme : themeOptions[0].id
}

const activeTheme = ref(resolveTheme())

const applyTheme = (themeId = activeTheme.value) => {
  if (typeof document === 'undefined') return
  const currentTheme = themeOptions.find((theme) => theme.id === themeId) || themeOptions[0]
  document.documentElement.dataset.theme = currentTheme.id
  document.documentElement.style.colorScheme = currentTheme.mode === 'light' ? 'light' : 'dark'
  document.documentElement.classList.toggle('dark', currentTheme.mode === 'dark')
}

const setTheme = (themeId) => {
  if (!isValidTheme(themeId)) return
  activeTheme.value = themeId
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, themeId)
  }
  applyTheme(themeId)
}

const themeMeta = computed(() => {
  return themeOptions.find((theme) => theme.id === activeTheme.value) || themeOptions[0]
})

if (typeof window !== 'undefined') {
  applyTheme(activeTheme.value)
}

export function useTheme() {
  return {
    themes: themeOptions,
    activeTheme,
    themeMeta,
    applyTheme,
    setTheme
  }
}
