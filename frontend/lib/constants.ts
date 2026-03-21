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

function pickRandom<T extends readonly string[]>(arr: T): string {
  return arr[Math.floor(Math.random() * arr.length)]
}

export const getRandomUserDogUrl    = () => pickRandom(DOG_USER_IMAGES)
export const getRandomTeacherDogUrl = () => pickRandom(DOG_TEACHER_IMAGES)
export const getRandomTogetherDogUrl = () => pickRandom(DOG_TOGETHER_IMAGES)

// 向后兼容（逐步迁移，不破坏未改到的地方）
export const DOG_GOLDEN  = '/dogs/golden.jpg'
export const DOG_WHITE   = '/dogs/white.jpg'
export const DOG_TOGETHER = '/dogs/together.jpg'
