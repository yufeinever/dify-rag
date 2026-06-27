'use client'

import { cn } from '@langgenius/dify-ui/cn'
import { toast } from '@langgenius/dify-ui/toast'
import * as React from 'react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useContextSelector } from 'use-context-selector'
import { CreateFromDSLModalTab } from '@/app/components/app/create-from-dsl-modal'
import { FileArrow01, FilePlus01, FilePlus02 } from '@/app/components/base/icons/src/vender/line/files'
import AppListContext from '@/context/app-list-context'
import { useProviderContext } from '@/context/provider-context'
import dynamic from '@/next/dynamic'
import {
  useRouter,
  useSearchParams,
} from '@/next/navigation'
import { AppModeEnum } from '@/types/app'

const CreateAppModal = dynamic(() => import('@/app/components/app/create-app-modal'), {
  ssr: false,
})
const CreateAppTemplateDialog = dynamic(() => import('@/app/components/app/create-app-dialog'), {
  ssr: false,
})
const CreateFromDSLModal = dynamic(() => import('@/app/components/app/create-from-dsl-modal'), {
  ssr: false,
})

type CreateAppCardProps = {
  className?: string
  isLoading?: boolean
  disabled?: boolean
  onSuccess?: () => void
  ref: React.RefObject<HTMLDivElement | null>
  selectedAppType?: string
}

const CreateAppCard = ({
  ref,
  className,
  isLoading = false,
  disabled = false,
  onSuccess,
  selectedAppType,
}: CreateAppCardProps) => {
  const { t } = useTranslation()
  const { onPlanInfoChanged } = useProviderContext()
  const searchParams = useSearchParams()
  const { replace } = useRouter()
  const dslUrl = searchParams.get('remoteInstallUrl') || undefined

  const [showNewAppTemplateDialog, setShowNewAppTemplateDialog] = useState(false)
  const [showNewAppModal, setShowNewAppModal] = useState(false)
  const [showCreateFromDSLModal, setShowCreateFromDSLModal] = useState(!!dslUrl)

  const notifyUnauthorized = () => toast.warning('无权限，请联系管理员授权')

  const handleUnavailableAction = (action: () => void) => {
    if (disabled) {
      notifyUnauthorized()
      return
    }
    action()
  }

  const defaultAppMode = useMemo(() => {
    if (!selectedAppType || selectedAppType === 'all')
      return undefined

    return Object.values(AppModeEnum).includes(selectedAppType as AppModeEnum)
      ? selectedAppType as AppModeEnum
      : undefined
  }, [selectedAppType])

  const activeTab = useMemo(() => {
    if (dslUrl)
      return CreateFromDSLModalTab.FROM_URL

    return undefined
  }, [dslUrl])

  const controlHideCreateFromTemplatePanel = useContextSelector(AppListContext, ctx => ctx.controlHideCreateFromTemplatePanel)
  useEffect(() => {
    if (controlHideCreateFromTemplatePanel > 0)
      // eslint-disable-next-line react/set-state-in-effect
      setShowNewAppTemplateDialog(false)
  }, [controlHideCreateFromTemplatePanel])

  return (
    <div
      ref={ref}
      className={cn(
        'relative col-span-1 inline-flex h-[160px] flex-col justify-between rounded-xl border-[0.5px] border-components-card-border bg-components-card-bg transition-opacity',
        isLoading && 'pointer-events-none opacity-50',
        disabled && 'opacity-50 grayscale',
        className,
      )}
    >
      {disabled && (
        <div className="absolute top-3 right-3 rounded-md border border-divider-subtle bg-background-section px-2 py-0.5 text-xs font-medium text-text-tertiary">无权限</div>
      )}
      <div className="grow rounded-t-xl p-2">
        <div className="px-6 pt-2 pb-1 text-xs leading-[18px] font-medium text-text-tertiary">{t('createApp', { ns: 'app' })}</div>
        <button type="button" aria-disabled={disabled} className="mb-1 flex w-full cursor-pointer items-center rounded-lg px-6 py-[7px] text-[13px] leading-[18px] font-medium text-text-tertiary hover:bg-state-base-hover hover:text-text-secondary disabled:cursor-not-allowed" onClick={() => handleUnavailableAction(() => setShowNewAppModal(true))}>
          <FilePlus01 className="mr-2 size-4 shrink-0" />
          {t('newApp.startFromBlank', { ns: 'app' })}
        </button>
        <button type="button" aria-disabled={disabled} className="flex w-full cursor-pointer items-center rounded-lg px-6 py-[7px] text-[13px] leading-[18px] font-medium text-text-tertiary hover:bg-state-base-hover hover:text-text-secondary disabled:cursor-not-allowed" onClick={() => handleUnavailableAction(() => setShowNewAppTemplateDialog(true))}>
          <FilePlus02 className="mr-2 size-4 shrink-0" />
          {t('newApp.startFromTemplate', { ns: 'app' })}
        </button>
        <button
          type="button"
          aria-disabled={disabled}
          onClick={() => handleUnavailableAction(() => setShowCreateFromDSLModal(true))}
          className="flex w-full cursor-pointer items-center rounded-lg px-6 py-[7px] text-[13px] leading-[18px] font-medium text-text-tertiary hover:bg-state-base-hover hover:text-text-secondary disabled:cursor-not-allowed"
        >
          <FileArrow01 className="mr-2 size-4 shrink-0" />
          {t('importDSL', { ns: 'app' })}
        </button>
      </div>

      {showNewAppModal && (
        <CreateAppModal
          show={showNewAppModal}
          onClose={() => setShowNewAppModal(false)}
          onSuccess={() => {
            onPlanInfoChanged()
            if (onSuccess)
              onSuccess()
          }}
          onCreateFromTemplate={() => {
            setShowNewAppTemplateDialog(true)
            setShowNewAppModal(false)
          }}
          defaultAppMode={defaultAppMode}
        />
      )}
      {showNewAppTemplateDialog && (
        <CreateAppTemplateDialog
          show={showNewAppTemplateDialog}
          onClose={() => setShowNewAppTemplateDialog(false)}
          onSuccess={() => {
            onPlanInfoChanged()
            if (onSuccess)
              onSuccess()
          }}
          onCreateFromBlank={() => {
            setShowNewAppModal(true)
            setShowNewAppTemplateDialog(false)
          }}
        />
      )}
      {showCreateFromDSLModal && (
        <CreateFromDSLModal
          show={showCreateFromDSLModal}
          onClose={() => {
            setShowCreateFromDSLModal(false)

            if (dslUrl)
              replace('/')
          }}
          activeTab={activeTab}
          dslUrl={dslUrl}
          onSuccess={() => {
            onPlanInfoChanged()
            if (onSuccess)
              onSuccess()
          }}
        />
      )}
    </div>
  )
}

CreateAppCard.displayName = 'CreateAppCard'

export default React.memo(CreateAppCard)
