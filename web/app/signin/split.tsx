'use client'
import type { FC } from 'react'
import { cn } from '@langgenius/dify-ui/cn'
import * as React from 'react'

type Props = {
  className?: string
}

const Split: FC<Props> = ({
  className,
}) => {
  return (
    <div
      className={cn('h-px w-full bg-[linear-gradient(90deg,rgba(255,255,255,0.01)_0%,rgba(255,255,255,0.12)_50.5%,rgba(255,255,255,0.01)_100%)]', className)}
    >
    </div>
  )
}
export default React.memo(Split)
