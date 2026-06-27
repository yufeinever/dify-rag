'use client'
import { cn } from '@langgenius/dify-ui/cn'
import { toast } from '@langgenius/dify-ui/toast'
import {
  RiAddLine,
  RiFunctionAddLine,
} from '@remixicon/react'
import * as React from 'react'
import { useTranslation } from 'react-i18next'
import { ApiConnectionMod } from '@/app/components/base/icons/src/vender/solid/development'
import Option from './option'

type CreateAppCardProps = {
  disabled?: boolean
}

const CreateAppCard = ({ disabled = false }: CreateAppCardProps) => {
  const { t } = useTranslation()
  const notifyUnauthorized = () => toast.warning('无权限，请联系管理员授权')

  return (
    <div className={cn('relative flex h-[190px] flex-col gap-y-0.5 rounded-xl bg-background-default-dimmed', disabled && 'opacity-50 grayscale')}>
      {disabled && (
        <div className="absolute top-3 right-3 z-10 rounded-md border border-divider-subtle bg-background-section px-2 py-0.5 text-xs font-medium text-text-tertiary">无权限</div>
      )}
      <div className="flex grow flex-col items-center justify-center p-2">
        <Option
          href="/datasets/create"
          disabled={disabled}
          onDisabledClick={notifyUnauthorized}
          Icon={RiAddLine}
          text={t('createDataset', { ns: 'dataset' })}
        />
        <Option
          href="/datasets/create-from-pipeline"
          disabled={disabled}
          onDisabledClick={notifyUnauthorized}
          Icon={RiFunctionAddLine}
          text={t('createFromPipeline', { ns: 'dataset' })}
        />
      </div>
      <div className="border-t-[0.5px] border-divider-subtle p-2">
        <Option
          href="/datasets/connect"
          disabled={disabled}
          onDisabledClick={notifyUnauthorized}
          Icon={ApiConnectionMod}
          text={t('connectDataset', { ns: 'dataset' })}
        />
      </div>
    </div>
  )
}

CreateAppCard.displayName = 'CreateAppCard'

export default CreateAppCard
