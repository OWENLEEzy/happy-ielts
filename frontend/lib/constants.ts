export const DOG_GOLDEN = 'https://i.pinimg.com/736x/4d/de/1f/4dde1f6accdebbc5d858bbff163b06c3.jpg'
export const DOG_WHITE = 'https://i.pinimg.com/736x/2f/66/f3/2f66f3078d5340540ac3c178cb8b261e.jpg'
export const DOG_TOGETHER =
  'https://i.pinimg.com/736x/27/76/b3/2776b30bd673a7eefb90d0bd87372bbb.jpg'

export const DOG_IMAGES = [
  // 1200x collection
  'https://i.pinimg.com/1200x/6b/cb/96/6bcb96b976025670b1fa1c331b416a48.jpg',
  'https://i.pinimg.com/1200x/4f/c4/2a/4fc42a007f2945d35e41f33d928f90c3.jpg',
  'https://i.pinimg.com/1200x/12/e2/9c/12e29cc930b89d9285c43b0c46b97c13.jpg',
  'https://i.pinimg.com/1200x/64/f1/7b/64f17b9daeb43c8819b3031b69604374.jpg',
  'https://i.pinimg.com/1200x/64/33/84/643384000e27c214fc8c623e0ec6d9b5.jpg',
  'https://i.pinimg.com/1200x/32/00/a0/3200a05b19c27dea9721156f221607ff.jpg',
  'https://i.pinimg.com/1200x/f4/2b/49/f42b491a715ee2a3df8834366d2beff3.jpg',
  'https://i.pinimg.com/1200x/96/05/7e/96057edd8358aa5dc35df7ffc49a07ad.jpg',
  'https://i.pinimg.com/1200x/84/3b/8d/843b8d4d029c5efe0ff2b2aca956e4d2.jpg',
  'https://i.pinimg.com/1200x/56/f2/d5/56f2d5db72c2aa8e8e10b8a3d5f78242.jpg',
  'https://i.pinimg.com/1200x/cf/51/56/cf515632f169122e40042ae6f26dae28.jpg',
  'https://i.pinimg.com/1200x/f8/32/a1/f832a17e15455eb3ee38919a753a4a8a.jpg',
] as const

export function getRandomDogUrl(): string {
  return DOG_IMAGES[Math.floor(Math.random() * DOG_IMAGES.length)]
}
