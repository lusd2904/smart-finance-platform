<template>
  <canvas ref="canvasRef" class="theme-background"></canvas>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  particleCount: {
    type: Number,
    default: 60
  },
  sweepIntervalMs: {
    type: Number,
    default: 6000
  }
})

const canvasRef = ref(null)

let ctx = null
let rafId = null
let particles = []
let width = 0
let height = 0
let dpr = 1
let lastFrameTime = 0
// 限制到约 30fps，兼顾低端设备性能
const FRAME_INTERVAL = 1000 / 30

let accentColor = '99, 102, 241'
let accentSecondary = '139, 92, 246'
let sweep = null
let nextSweepAt = 0

function hexToRgbString(hex, fallback) {
  const value = (hex || '').trim().replace('#', '')
  if (value.length !== 6) return fallback
  const r = parseInt(value.slice(0, 2), 16)
  const g = parseInt(value.slice(2, 4), 16)
  const b = parseInt(value.slice(4, 6), 16)
  if ([r, g, b].some(Number.isNaN)) return fallback
  return `${r}, ${g}, ${b}`
}

function readAccentColors() {
  const styles = getComputedStyle(document.documentElement)
  accentColor = hexToRgbString(styles.getPropertyValue('--accent'), accentColor)
  accentSecondary = hexToRgbString(styles.getPropertyValue('--accent-secondary'), accentSecondary)
}

function resize() {
  const canvas = canvasRef.value
  if (!canvas) return
  const parent = canvas.parentElement
  width = parent ? parent.clientWidth : window.innerWidth
  height = parent ? parent.clientHeight : window.innerHeight
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = width * dpr
  canvas.height = height * dpr
  canvas.style.width = width + 'px'
  canvas.style.height = height + 'px'
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function createParticles() {
  particles = Array.from({ length: props.particleCount }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    r: Math.random() * 1.6 + 0.6,
    vx: (Math.random() - 0.5) * 0.15,
    vy: (Math.random() - 0.5) * 0.15,
    baseAlpha: Math.random() * 0.35 + 0.15,
    phase: Math.random() * Math.PI * 2
  }))
}

function scheduleSweep(now) {
  nextSweepAt = now + props.sweepIntervalMs + Math.random() * props.sweepIntervalMs
}

function drawSweep(now) {
  if (!sweep) {
    if (now < nextSweepAt) return
    sweep = { start: now, duration: 1600 }
  }
  const t = (now - sweep.start) / sweep.duration
  if (t >= 1) {
    sweep = null
    scheduleSweep(now)
    return
  }
  const span = width + height
  const pos = t * span - height
  const gradient = ctx.createLinearGradient(pos, 0, pos + height, height)
  gradient.addColorStop(0, `rgba(${accentColor}, 0)`)
  gradient.addColorStop(0.5, `rgba(${accentSecondary}, 0.1)`)
  gradient.addColorStop(1, `rgba(${accentColor}, 0)`)
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, width, height)
}

function drawParticles(now) {
  particles.forEach(p => {
    p.x += p.vx
    p.y += p.vy
    if (p.x < 0) p.x = width
    else if (p.x > width) p.x = 0
    if (p.y < 0) p.y = height
    else if (p.y > height) p.y = 0

    const alpha = Math.max(p.baseAlpha + Math.sin(now / 1000 + p.phase) * 0.1, 0.05)
    ctx.beginPath()
    ctx.fillStyle = `rgba(${accentColor}, ${alpha})`
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fill()
  })
}

function draw(timestamp) {
  rafId = requestAnimationFrame(draw)
  if (timestamp - lastFrameTime < FRAME_INTERVAL) return
  lastFrameTime = timestamp

  ctx.clearRect(0, 0, width, height)
  drawParticles(timestamp)
  drawSweep(timestamp)
}

function handleResize() {
  resize()
  createParticles()
}

onMounted(() => {
  const canvas = canvasRef.value
  if (!canvas) return
  ctx = canvas.getContext('2d')
  readAccentColors()
  resize()
  createParticles()
  nextSweepAt = performance.now() + 2000
  rafId = requestAnimationFrame(draw)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId)
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.theme-background {
  position: absolute;
  inset: 0;
  display: block;
  pointer-events: none;
}
</style>
