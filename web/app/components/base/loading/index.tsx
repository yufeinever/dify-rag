'use client'

import { cn } from '@langgenius/dify-ui/cn'
import { useTranslation } from 'react-i18next'
import './style.css'

type ILoadingProps = {
  type?: 'area' | 'app'
  className?: string
}

const Loading = (props?: ILoadingProps) => {
  const { type = 'area', className } = props || {}
  const { t } = useTranslation()

  return (
    <div
      className={cn(
        'flex w-full items-center justify-center',
        type === 'app' && 'h-full',
        className,
      )}
      role="status"
      aria-live="polite"
      aria-label={t('loading', { ns: 'appApi' })}
    >
      <span className="mmb-loading-asset" aria-hidden="true">
        <img
          className="mmb-loading-image"
          src="/custom-assets/mmb-loading/mmb-bear-bottle-transparent.png"
          alt=""
        />
        <span className="mmb-beer-fill" />
      </span>
    </div>
  )
}

export default Loading
