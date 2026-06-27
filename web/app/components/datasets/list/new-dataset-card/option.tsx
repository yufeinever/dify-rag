import { cn } from '@langgenius/dify-ui/cn'
import * as React from 'react'
import Link from '@/next/link'

type OptionProps = {
  Icon: React.ComponentType<{ className?: string }>
  text: string
  href: string
  disabled?: boolean
  onDisabledClick?: () => void
}

const Option = ({
  Icon,
  text,
  href,
  disabled = false,
  onDisabledClick,
}: OptionProps) => {
  return (
    <Link
      type="button"
      aria-disabled={disabled}
      className={cn(
        'flex w-full items-center gap-x-2 rounded-lg bg-transparent px-4 py-2 text-text-tertiary shadow-shadow-shadow-3 hover:bg-background-default-dodge hover:text-text-secondary hover:shadow-xs',
        disabled && 'cursor-not-allowed hover:bg-transparent hover:text-text-tertiary hover:shadow-none',
      )}
      href={disabled ? '#' : href}
      onClick={(event) => {
        if (!disabled)
          return
        event.preventDefault()
        onDisabledClick?.()
      }}
    >
      <Icon className="size-4 shrink-0" />
      <span className="grow text-left system-sm-medium">{text}</span>
    </Link>
  )
}

export default React.memo(Option)
