'use client'
import type { FC } from 'react'
import { cn } from '@langgenius/dify-ui/cn'
import useTheme from '@/hooks/use-theme'
import { basePath } from '@/utils/var'

export type LogoStyle = 'default' | 'monochromeWhite'

export const logoPathMap: Record<LogoStyle, string> = {
  default: '/custom-assets/mmb-logo/logo-embedded-chat-avatar.png',
  monochromeWhite: '/custom-assets/mmb-logo/logo-embedded-chat-avatar.png',
}

export type LogoSize = 'large' | 'medium' | 'small'

export const logoSizeMap: Record<LogoSize, string> = {
  large: 'size-10',
  medium: 'size-8',
  small: 'size-5',
}

type DifyLogoProps = {
  style?: LogoStyle
  size?: LogoSize
  className?: string
}

const DifyLogo: FC<DifyLogoProps> = ({
  style = 'default',
  size = 'medium',
  className,
}) => {
  const { theme } = useTheme()
  const themedStyle = (theme === 'dark' && style === 'default') ? 'monochromeWhite' : style

  return (
    <img
      src={`${basePath}${logoPathMap[themedStyle]}`}
      className={cn('block object-contain', logoSizeMap[size], className)}
      alt="MMBAI logo"
    />
  )
}

export default DifyLogo
