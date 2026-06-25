import type { FC } from 'react'
import type { Area } from 'react-easy-crop'
import type { OnImageInput } from './ImageInput'
import type { AppIconType, ImageFile } from '@/types/app'
import { Button } from '@langgenius/dify-ui/button'
import { cn } from '@langgenius/dify-ui/cn'
import { Dialog, DialogContent } from '@langgenius/dify-ui/dialog'
import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { DISABLE_UPLOAD_IMAGE_AS_ICON } from '@/config'
import Divider from '../divider'
import EmojiPickerInner from '../emoji-picker/Inner'
import { useLocalFileUploader } from '../image-uploader/hooks'
import { BUILTIN_BEAR_ICONS, DEFAULT_BUILTIN_BEAR_ICON, TAB_BUILTIN_BEAR_ICON } from './builtin-bear-icons'
import ImageInput from './ImageInput'
import s from './style.module.css'
import getCroppedImg from './utils'

export type AppIconEmojiSelection = {
  type: 'emoji'
  icon: string
  background: string
}

export type AppIconImageSelection = {
  type: 'image'
  fileId: string
  url: string
}

export type AppIconSelection = AppIconEmojiSelection | AppIconImageSelection

type AppIconPickerTab = AppIconType | 'bear'

type AppIconPickerProps = {
  onSelect?: (payload: AppIconSelection) => void
  onClose?: () => void
  initialEmoji?: {
    icon: string
    background?: string | null
  }
  className?: string
}

const AppIconPicker: FC<AppIconPickerProps> = ({
  onSelect,
  onClose,
  initialEmoji,
}) => {
  const { t } = useTranslation()

  const tabs = [
    { key: 'emoji', label: t('iconPicker.emoji', { ns: 'app' }), icon: <span className="text-lg">🤖</span> },
    { key: 'bear', label: t('iconPicker.bear', { ns: 'app' }), icon: <img src={TAB_BUILTIN_BEAR_ICON.path} alt="" className="size-4 rounded" /> },
    ...(!DISABLE_UPLOAD_IMAGE_AS_ICON ? [{ key: 'image', label: t('iconPicker.image', { ns: 'app' }), icon: <span className="i-ri-image-circle-ai-line size-4" /> }] : []),
  ]
  const [activeTab, setActiveTab] = useState<AppIconPickerTab>('emoji')
  const [selectedBearIcon, setSelectedBearIcon] = useState(DEFAULT_BUILTIN_BEAR_ICON)

  const [emoji, setEmoji] = useState<{ emoji: string, background: string }>()
  const handleSelectEmoji = useCallback((emoji: string, background: string) => {
    setEmoji({ emoji, background })
  }, [setEmoji])

  const [uploading, setUploading] = useState<boolean>()

  const { handleLocalFileUpload } = useLocalFileUploader({
    limit: 3,
    disabled: false,
    onUpload: (imageFile: ImageFile) => {
      if (imageFile.fileId) {
        setUploading(false)
        onSelect?.({
          type: 'image',
          fileId: imageFile.fileId,
          url: imageFile.url,
        })
      }
    },
  })

  type InputImageInfo = { file: File } | { tempUrl: string, croppedAreaPixels: Area, fileName: string }
  const [inputImageInfo, setInputImageInfo] = useState<InputImageInfo>()

  const handleImageInput: OnImageInput = async (isCropped: boolean, fileOrTempUrl: string | File, croppedAreaPixels?: Area, fileName?: string) => {
    setInputImageInfo(
      isCropped
        ? { tempUrl: fileOrTempUrl as string, croppedAreaPixels: croppedAreaPixels!, fileName: fileName! }
        : { file: fileOrTempUrl as File },
    )
  }

  const handleSelect = async () => {
    if (activeTab === 'emoji') {
      if (emoji) {
        onSelect?.({
          type: 'emoji',
          icon: emoji.emoji,
          background: emoji.background,
        })
      }
      return
    }

    if (activeTab === 'bear') {
      onSelect?.({
        type: 'image',
        fileId: selectedBearIcon.path,
        url: selectedBearIcon.path,
      })
      return
    }

    if (!inputImageInfo)
      return
    setUploading(true)
    if ('file' in inputImageInfo) {
      handleLocalFileUpload(inputImageInfo.file)
      return
    }
    const blob = await getCroppedImg(inputImageInfo.tempUrl, inputImageInfo.croppedAreaPixels, inputImageInfo.fileName)
    const file = new File([blob], inputImageInfo.fileName, { type: blob.type })
    handleLocalFileUpload(file)
  }

  return (
    <Dialog open>
      <DialogContent className={cn('w-full overflow-hidden! border-none text-left align-middle', s.container, 'h-[min(536px,calc(100dvh-2rem))]! max-h-none! w-[420px]! p-0!')}>

        <div className="w-full p-2 pb-0">
          <div className="flex items-center justify-center gap-2 rounded-xl bg-background-body p-1 text-text-primary">
            {tabs.map(tab => (
              <button
                type="button"
                key={tab.key}
                className={cn(
                  'flex h-8 flex-1 shrink-0 items-center justify-center rounded-lg p-2 system-sm-medium text-text-tertiary',
                  activeTab === tab.key && 'bg-components-main-nav-nav-button-bg-active text-text-accent shadow-md',
                )}
                onClick={() => setActiveTab(tab.key as AppIconPickerTab)}
              >
                {tab.icon}
                {' '}
&nbsp;
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {activeTab === 'emoji' && (
          <EmojiPickerInner
            className={cn('flex-1 overflow-hidden pt-2')}
            emoji={initialEmoji?.icon}
            background={initialEmoji?.background ?? undefined}
            onSelect={handleSelectEmoji}
          />
        )}
        {activeTab === 'bear' && (
          <div className="flex-1 overflow-y-auto p-3">
            <div className="mb-3 grid grid-cols-4 gap-2">
              {BUILTIN_BEAR_ICONS.map(icon => (
                <button
                  type="button"
                  key={icon.id}
                  title={icon.label}
                  aria-label={icon.label}
                  className={cn(
                    'relative aspect-square overflow-hidden rounded-xl border bg-background-default p-1 transition hover:border-components-button-primary-bg hover:bg-state-base-hover',
                    selectedBearIcon.id === icon.id ? 'border-components-button-primary-bg ring-2 ring-components-button-primary-bg/20' : 'border-divider-regular',
                  )}
                  onClick={() => setSelectedBearIcon(icon)}
                >
                  <img src={icon.path} alt="" className="size-full rounded-lg object-cover" />
                </button>
              ))}
            </div>
          </div>
        )}
        {activeTab === 'image' && <ImageInput className={cn('flex-1 overflow-hidden')} onImageInput={handleImageInput} />}

        <Divider className="m-0" />
        <div className="flex w-full items-center justify-center gap-2 p-3">
          <Button className="w-full" onClick={() => onClose?.()}>
            {t('iconPicker.cancel', { ns: 'app' })}
          </Button>

          <Button variant="primary" className="w-full" disabled={uploading} loading={uploading} onClick={handleSelect}>
            {t('iconPicker.ok', { ns: 'app' })}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default AppIconPicker
