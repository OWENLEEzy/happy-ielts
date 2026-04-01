'use client'

import { useState } from 'react'
import Image from 'next/image'
import { cn } from '@/lib/utils'
import { getRandomDogUrl, type DogRole } from '@/lib/constants'

type DogAvatarProps = {
  role: DogRole
  size: number
  emphasis?: 'inline' | 'card' | 'hero'
  alt: string
  className?: string
}

const ROLE_FRAME_CLASSES: Record<DogRole, string> = {
  teacher: 'border-primary/20 bg-tertiary-container/25 shadow-primary/10',
  user: 'border-secondary/20 bg-secondary-container/25 shadow-secondary/10',
  relationship: 'border-primary/25 bg-primary/10 shadow-primary/15',
}

const EMPHASIS_FRAME_CLASSES: Record<NonNullable<DogAvatarProps['emphasis']>, string> = {
  inline: 'shadow-sm',
  card: 'shadow-md',
  hero: 'shadow-lg',
}

export function DogAvatar({
  role,
  size,
  emphasis = 'inline',
  alt,
  className,
}: DogAvatarProps) {
  const [dogUrl] = useState(() => getRandomDogUrl(role))

  return (
    <div
      data-dog-role={role}
      data-dog-emphasis={emphasis}
      className={cn(
        'relative shrink-0 overflow-hidden rounded-full border',
        ROLE_FRAME_CLASSES[role],
        EMPHASIS_FRAME_CLASSES[emphasis],
        className,
      )}
      style={{ width: size, height: size }}
    >
      <Image src={dogUrl} fill sizes={`${size}px`} className="object-cover" alt={alt} />
    </div>
  )
}
