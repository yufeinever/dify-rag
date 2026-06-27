'use client'

import { cn } from '@langgenius/dify-ui/cn'
import { useTranslation } from 'react-i18next'
import Link from '@/next/link'
import { useSelectedLayoutSegment } from '@/next/navigation'

type ToolsNavProps = {
  className?: string
}

const ToolsNav = ({
  className,
}: ToolsNavProps) => {
  const { t } = useTranslation()
  const selectedSegment = useSelectedLayoutSegment()
  const activated = selectedSegment === 'tools'

  return (
    <Link
      href="/tools"
      className={cn(className, 'group')}
    >
      <div
        className={cn('relative flex h-8 flex-row items-center justify-center gap-0.5 rounded-xl border border-transparent p-1.5 system-sm-medium', activated && 'border-components-main-nav-nav-button-border bg-components-main-nav-nav-button-bg-active text-components-main-nav-nav-button-text shadow-md', !activated && 'text-text-tertiary hover:bg-state-base-hover hover:text-text-secondary')}
      >
        <div className="mr-0.5 flex size-5 items-center justify-center">
          {
            activated
              ? <span aria-hidden className="i-ri-hammer-fill size-4" data-testid="icon-hammer-fill" />
              : <span aria-hidden className="i-ri-hammer-line size-4" data-testid="icon-hammer-line" />
          }
        </div>
        <span className="px-0.5">{t('menus.tools', { ns: 'common' })}</span>
      </div>
    </Link>
  )
}

export default ToolsNav
