<template>
  <canvas ref="canvasRef" class="cyber-canvas"></canvas>
</template>

<script setup>
/**
 * 移植自 longbridge web-portal CyberBackground：
 * 0/1/Hex 神经元节点 + 节点连线 + 穿梭光带
 */
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import useSettingsStore from '@/store/modules/settings'

const canvasRef = ref(null)
const settingsStore = useSettingsStore()

let animationFrameId = 0
let ctx = null
let canvas = null
let particles = []
let shootingLines = []

const MAX_PARTICLES = 70
const CONNECTION_DISTANCE = 160
const SPEED_MULTIPLIER = 0.32

class Particle {
  constructor(w, h) {
    this.x = Math.random() * w
    this.y = Math.random() * h
    this.vx = (Math.random() - 0.5) * SPEED_MULTIPLIER
    this.vy = (Math.random() - 0.5) * SPEED_MULTIPLIER
    const charCode = Math.random() > 0.6
      ? (Math.random() > 0.5 ? 48 : 49)
      : (65 + Math.floor(Math.random() * 6))
    this.text = String.fromCharCode(charCode)
    this.size = Math.random() * 8 + 10
  }
  update(w, h) {
    this.x += this.vx
    this.y += this.vy
    if (this.x < 0 || this.x > w) this.vx *= -1
    if (this.y < 0 || this.y > h) this.vy *= -1
  }
  draw(c, color) {
    c.font = `bold ${this.size}px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`
    c.fillStyle = color
    c.fillText(this.text, this.x, this.y)
  }
}

class ShootingLine {
  constructor(w, h) {
    this.reset(w, h)
    this.progress = Math.random()
  }
  reset(w, h) {
    this.canvasWidth = w
    this.canvasHeight = h
    this.length = Math.random() * 400 + 200
    this.speed = Math.random() * 0.003 + 0.001
    this.progress = 0
    const dir = Math.floor(Math.random() * 4)
    if (dir === 0) {
      this.startX = -this.length
      this.startY = Math.random() * h
      this.endX = w + this.length
      this.endY = this.startY + (Math.random() - 0.5) * 200
    } else if (dir === 1) {
      this.startX = w + this.length
      this.startY = Math.random() * h
      this.endX = -this.length
      this.endY = this.startY + (Math.random() - 0.5) * 200
    } else if (dir === 2) {
      this.startX = -this.length
      this.startY = -this.length
      this.endX = w + this.length
      this.endY = h + this.length
    } else {
      this.startX = w + this.length
      this.startY = h + this.length
      this.endX = -this.length
      this.endY = -this.length
    }
  }
  update() {
    this.progress += this.speed
    if (this.progress > 1.2) this.reset(this.canvasWidth, this.canvasHeight)
  }
  draw(c, isDark) {
    const currentX = this.startX + (this.endX - this.startX) * this.progress
    const currentY = this.startY + (this.endY - this.startY) * this.progress
    const angle = Math.atan2(this.endY - this.startY, this.endX - this.startX)
    const tailX = currentX - Math.cos(angle) * this.length
    const tailY = currentY - Math.sin(angle) * this.length
    const grad = c.createLinearGradient(tailX, tailY, currentX, currentY)
    if (isDark) {
      grad.addColorStop(0, 'rgba(56, 189, 248, 0)')
      grad.addColorStop(1, 'rgba(56, 189, 248, 0.65)')
    } else {
      grad.addColorStop(0, 'rgba(2, 132, 199, 0)')
      grad.addColorStop(1, 'rgba(2, 132, 199, 0.45)')
    }
    c.beginPath()
    c.moveTo(tailX, tailY)
    c.lineTo(currentX, currentY)
    c.strokeStyle = grad
    c.lineWidth = 2
    c.stroke()
    c.beginPath()
    c.arc(currentX, currentY, 3, 0, Math.PI * 2)
    c.fillStyle = isDark ? '#bae6fd' : '#0284c7'
    c.shadowBlur = 16
    c.shadowColor = isDark ? '#38bdf8' : '#0284c7'
    c.fill()
    c.shadowBlur = 0
  }
}

function resizeCanvas() {
  if (!canvas) return
  canvas.width = window.innerWidth
  canvas.height = window.innerHeight
  const count = Math.min(MAX_PARTICLES, Math.floor((canvas.width * canvas.height) / 14000))
  if (particles.length === 0) {
    particles = Array.from({ length: count }, () => new Particle(canvas.width, canvas.height))
  } else if (particles.length < count) {
    particles.push(...Array.from({ length: count - particles.length }, () => new Particle(canvas.width, canvas.height)))
  }
  if (shootingLines.length === 0) {
    shootingLines = Array.from({ length: 6 }, () => new ShootingLine(canvas.width, canvas.height))
  } else {
    shootingLines.forEach(line => line.reset(canvas.width, canvas.height))
  }
}

function draw() {
  if (!ctx || !canvas) return
  const isDark = !!settingsStore.isDark || document.documentElement.classList.contains('dark') ||
    document.documentElement.getAttribute('data-theme') === 'glass-dark'
  const particleColor = isDark ? 'rgba(56, 189, 248, 0.85)' : 'rgba(2, 132, 199, 0.7)'
  const lineColorRGB = isDark ? '56, 189, 248' : '2, 132, 199'

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  for (let i = 0; i < shootingLines.length; i++) {
    shootingLines[i].update()
    shootingLines[i].draw(ctx, isDark)
  }

  for (let i = 0; i < particles.length; i++) {
    const p1 = particles[i]
    p1.update(canvas.width, canvas.height)
    for (let j = i + 1; j < particles.length; j++) {
      const p2 = particles[j]
      const dx = p1.x - p2.x
      const dy = p1.y - p2.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < CONNECTION_DISTANCE) {
        const opacity = (1 - dist / CONNECTION_DISTANCE) * 0.35
        ctx.beginPath()
        ctx.moveTo(p1.x, p1.y)
        ctx.lineTo(p2.x, p2.y)
        ctx.strokeStyle = `rgba(${lineColorRGB}, ${opacity})`
        ctx.lineWidth = 1
        ctx.stroke()
      }
    }
    p1.draw(ctx, particleColor)
  }
  animationFrameId = requestAnimationFrame(draw)
}

onMounted(() => {
  canvas = canvasRef.value
  if (!canvas) return
  ctx = canvas.getContext('2d')
  resizeCanvas()
  animationFrameId = requestAnimationFrame(draw)
  window.addEventListener('resize', resizeCanvas)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationFrameId)
  window.removeEventListener('resize', resizeCanvas)
})

watch(() => settingsStore.isDark, () => {
  // 主题切换时下一帧自动用新配色
})
</script>

<style scoped>
.cyber-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  pointer-events: none;
  z-index: 0;
}
</style>
