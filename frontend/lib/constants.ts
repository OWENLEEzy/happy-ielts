// 🤍 白色狗 — 用户/学生头像
export const DOG_USER_IMAGES = [
  '/dogs/dog2.jpg',   // 白色狗拿手机
  '/dogs/dog11.jpg',  // 白色狗抱爱心
  '/dogs/dog12.jpg',  // 白色狗捧花
  '/dogs/white.jpg',  // 白色狗抱爱心（另一款）
] as const

// 💛 黄色狗 — 老师/教授头像
export const DOG_TEACHER_IMAGES = [
  '/dogs/dog8.jpg',   // 黄色狗抱爱心
  '/dogs/golden.jpg', // 黄色狗花型
] as const

// 🫶 合照 — 庆祝完成时出现
export const DOG_TOGETHER_IMAGES = [
  '/dogs/dog1.jpg',
  '/dogs/dog3.jpg',
  '/dogs/dog4.jpg',
  '/dogs/dog5.jpg',
  '/dogs/dog6.jpg',
  '/dogs/dog7.jpg',
  '/dogs/dog9.jpg',
  '/dogs/dog10.jpg',
  '/dogs/together.jpg',
] as const

export type DogRole = 'teacher' | 'user' | 'relationship'

function pickRandom<T extends readonly string[]>(arr: T): string {
  return arr[Math.floor(Math.random() * arr.length)]
}

function hashSeed(seed: string): number {
  let hash = 0
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
  }
  return hash
}

function pickStable<T extends readonly string[]>(arr: T, seedKey: string): string {
  return arr[hashSeed(seedKey) % arr.length]
}

export function getRandomDogUrl(role: DogRole): string {
  switch (role) {
    case 'teacher':
      return pickRandom(DOG_TEACHER_IMAGES)
    case 'user':
      return pickRandom(DOG_USER_IMAGES)
    case 'relationship':
      return pickRandom(DOG_TOGETHER_IMAGES)
  }
}

export function getSeededDogUrl(role: DogRole, seedKey: string): string {
  switch (role) {
    case 'teacher':
      return pickStable(DOG_TEACHER_IMAGES, `teacher:${seedKey}`)
    case 'user':
      return pickStable(DOG_USER_IMAGES, `user:${seedKey}`)
    case 'relationship':
      return pickStable(DOG_TOGETHER_IMAGES, `relationship:${seedKey}`)
  }
}

export function getDogUrl(role: DogRole, seedKey?: string): string {
  return seedKey ? getSeededDogUrl(role, seedKey) : getRandomDogUrl(role)
}

export const getRandomUserDogUrl = () => getRandomDogUrl('user')
export const getRandomTeacherDogUrl = () => getRandomDogUrl('teacher')
export const getRandomTogetherDogUrl = () => getRandomDogUrl('relationship')

// 向后兼容（逐步迁移，不破坏未改到的地方）
export const DOG_GOLDEN  = '/dogs/golden.jpg'
export const DOG_WHITE   = '/dogs/white.jpg'
export const DOG_TOGETHER = '/dogs/together.jpg'
