<template>
  <canvas ref="canvasRef" class="cyber-canvas"></canvas>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useTheme } from '../../composables/useTheme.js'

const canvasRef = ref(null)
const { activeTheme } = useTheme()

let animationFrameId
let ctx
let canvas
let particles = []
let shootingLines = []

const MAX_PARTICLES = 60 // 神经元节点数量
const CONNECTION_DISTANCE = 160 // 连线距离
const SPEED_MULTIPLIER = 0.3 // 节点移动极慢速

class Particle {
  constructor(canvasWidth, canvasHeight) {
    this.x = Math.random() * canvasWidth
    this.y = Math.random() * canvasHeight
    // 随机二维极慢速
    this.vx = (Math.random() - 0.5) * SPEED_MULTIPLIER
    this.vy = (Math.random() - 0.5) * SPEED_MULTIPLIER
    
    // 节点显示 0/1/Hex
    const charCode = Math.random() > 0.6 
      ? (Math.random() > 0.5 ? 48 : 49) 
      : (65 + Math.floor(Math.random() * 6))
    this.text = String.fromCharCode(charCode)
    this.size = Math.random() * 8 + 10 
  }

  update(canvasWidth, canvasHeight) {
    this.x += this.vx
    this.y += this.vy

    // 碰壁反弹
    if (this.x < 0 || this.x > canvasWidth) this.vx *= -1
    if (this.y < 0 || this.y > canvasHeight) this.vy *= -1
  }

  draw(ctx, color) {
    ctx.font = `bold ${this.size}px Orbitron, monospace`
    ctx.fillStyle = color
    ctx.fillText(this.text, this.x, this.y)
  }
}

// 长的穿梭线条（不再是下雨，而是各个方向随机穿梭的极光线）
class ShootingLine {
  constructor(canvasWidth, canvasHeight) {
    this.reset(canvasWidth, canvasHeight)
    this.progress = Math.random() // 初始随机进度，避免一开始空荡荡
  }

  reset(canvasWidth, canvasHeight) {
    this.canvasWidth = canvasWidth
    this.canvasHeight = canvasHeight
    this.length = Math.random() * 400 + 200 // 非常长的线条 200~600px
    this.speed = Math.random() * 0.003 + 0.001 // 运动速度
    this.progress = 0
    
    // 随机方向 0: 左至右, 1: 右至左, 2: 坐上到右下, 3: 右下到左上
    // 没有纯粹从上到下的下雨，全是穿梭感
    const dir = Math.floor(Math.random() * 4)
    if (dir === 0) {
      this.startX = -this.length
      this.startY = Math.random() * canvasHeight
      this.endX = canvasWidth + this.length
      this.endY = this.startY + (Math.random() - 0.5) * 200 // 略带倾斜
    } else if (dir === 1) {
      this.startX = canvasWidth + this.length
      this.startY = Math.random() * canvasHeight
      this.endX = -this.length
      this.endY = this.startY + (Math.random() - 0.5) * 200
    } else if (dir === 2) {
      this.startX = -this.length
      this.startY = -this.length
      this.endX = canvasWidth + this.length
      this.endY = canvasHeight + this.length
    } else {
      this.startX = canvasWidth + this.length
      this.startY = canvasHeight + this.length
      this.endX = -this.length
      this.endY = -this.length
    }
  }

  update() {
    this.progress += this.speed
    if (this.progress > 1.2) {
      this.reset(this.canvasWidth, this.canvasHeight)
    }
  }

  draw(ctx, isDark) {
    const currentX = this.startX + (this.endX - this.startX) * this.progress
    const currentY = this.startY + (this.endY - this.startY) * this.progress
    
    // 使用三角函数计算长长的尾迹
    const angle = Math.atan2(this.endY - this.startY, this.endX - this.startX)
    const tailX = currentX - Math.cos(angle) * this.length
    const tailY = currentY - Math.sin(angle) * this.length

    const grad = ctx.createLinearGradient(tailX, tailY, currentX, currentY)
    if (isDark) {
      grad.addColorStop(0, 'rgba(56, 189, 248, 0)')
      grad.addColorStop(1, 'rgba(56, 189, 248, 0.6)') // 天蓝色光束
    } else {
      grad.addColorStop(0, 'rgba(2, 132, 199, 0)')
      grad.addColorStop(1, 'rgba(2, 132, 199, 0.4)')
    }

    ctx.beginPath()
    ctx.moveTo(tailX, tailY)
    ctx.lineTo(currentX, currentY)
    ctx.strokeStyle = grad
    ctx.lineWidth = 2
    ctx.stroke()
    
    // 发光头部
    ctx.beginPath()
    ctx.arc(currentX, currentY, 3, 0, Math.PI * 2)
    ctx.fillStyle = isDark ? '#bae6fd' : '#0284c7'
    ctx.shadowBlur = 15
    ctx.shadowColor = isDark ? '#38bdf8' : '#0284c7'
    ctx.fill()
    ctx.shadowBlur = 0 
  }
}

const resizeCanvas = () => {
  if (!canvas) return
  canvas.width = window.innerWidth
  canvas.height = window.innerHeight
  
  // 重新生成节点
  const count = Math.min(MAX_PARTICLES, Math.floor((canvas.width * canvas.height) / 15000))
  if (particles.length === 0) {
    particles = Array.from({ length: count }, () => new Particle(canvas.width, canvas.height))
  } else if (particles.length < count) {
    const extra = Array.from({ length: count - particles.length }, () => new Particle(canvas.width, canvas.height))
    particles.push(...extra)
  }

  // 生成长线条
  if (shootingLines.length === 0) {
    shootingLines = Array.from({ length: 5 }, () => new ShootingLine(canvas.width, canvas.height))
  } else {
    shootingLines.forEach(line => line.reset(canvas.width, canvas.height))
  }
}

const draw = () => {
  if (!ctx || !canvas) return
  
  const isDark = activeTheme.value === 'glass-dark'
  const particleColor = isDark ? 'rgba(56, 189, 248, 0.8)' : 'rgba(2, 132, 199, 0.65)' 
  const lineColorRGB = isDark ? '56, 189, 248' : '2, 132, 199'
  
  // 核心修复：必须使用 clearRect 保证全透明，绝对不能用 fillRect 积累背景色，否则会遮盖底层的流光网格！
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  
  // 绘制长线条
  for (let i = 0; i < shootingLines.length; i++) {
    shootingLines[i].update()
    shootingLines[i].draw(ctx, isDark)
  }

  // 绘制节点和互相之间的短连线
  for (let i = 0; i < particles.length; i++) {
    const p1 = particles[i]
    p1.update(canvas.width, canvas.height)
    
    for (let j = i + 1; j < particles.length; j++) {
      const p2 = particles[j]
      const dx = p1.x - p2.x
      const dy = p1.y - p2.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      
      if (dist < CONNECTION_DISTANCE) {
        const opacity = (1 - dist / CONNECTION_DISTANCE) * 0.3
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
  ctx = canvas.getContext('2d')
  
  window.addEventListener('resize', resizeCanvas)
  resizeCanvas()
  
  draw()
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCanvas)
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
  }
})
</script>

<style scoped>
.cyber-canvas {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: -3; /* 保证底部的 css gradient 能透上来 */
  pointer-events: none;
  opacity: 0.7; 
}
</style>
