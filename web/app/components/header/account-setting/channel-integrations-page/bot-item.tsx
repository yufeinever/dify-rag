import type { ChannelIntegrationBot } from '@/service/channel-integrations'
import {
  AlertDialog,
  AlertDialogActions,
  AlertDialogCancelButton,
  AlertDialogConfirmButton,
  AlertDialogContent,
  AlertDialogTitle,
} from '@langgenius/dify-ui/alert-dialog'
import { Button } from '@langgenius/dify-ui/button'
import { toast } from '@langgenius/dify-ui/toast'
import { useMemo, useState } from 'react'
import { useDeleteChannelIntegrationBot } from '@/service/channel-integrations'

const purposeLabels: Record<string, string> = {
  default: '默认聊天',
  copywriting: '文案',
  poster: '海报',
}

type BotItemProps = {
  bot: ChannelIntegrationBot
  onEdit: (bot: ChannelIntegrationBot) => void
}

export function BotItem({ bot, onEdit }: BotItemProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const deleteMutation = useDeleteChannelIntegrationBot()
  const bindingsText = useMemo(() => {
    if (!bot.bindings.length)
      return '未绑定应用'
    return bot.bindings.map(binding => `${purposeLabels[binding.purpose] ?? binding.purpose}：${binding.app_name ?? binding.app_id}`).join(' · ')
  }, [bot.bindings])
  const verifiedText = bot.last_verified_at
    ? new Date(bot.last_verified_at * 1000).toLocaleString()
    : '未验证'

  const handleCopy = async () => {
    await navigator.clipboard.writeText(bot.callback_url)
    toast.success('回调地址已复制')
  }

  const handleDelete = () => {
    deleteMutation.mutate(bot.id, {
      onSuccess: () => setShowDeleteConfirm(false),
    })
  }

  return (
    <div className="group mb-2 rounded-xl border-[0.5px] border-transparent bg-components-input-bg-normal p-4 hover:border-components-input-border-active hover:shadow-xs">
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-sm font-semibold text-white">飞</div>
        <div className="min-w-0 grow">
          <div className="flex items-center gap-2">
            <div className="truncate system-md-semibold text-text-primary">{bot.name}</div>
            <span className={bot.enabled ? 'rounded-md bg-state-success-hover px-1.5 py-0.5 text-xs text-text-success' : 'rounded-md bg-state-destructive-hover px-1.5 py-0.5 text-xs text-text-destructive'}>
              {bot.enabled ? '已启用' : '已停用'}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-text-tertiary">
            <span>
              飞书 Bot · 绑定
              {' '}
              {bot.bindings.length}
              {' '}
              个应用
            </span>
            <span>
              最后验证：
              {verifiedText}
            </span>
          </div>
          <div className="mt-2 truncate text-xs text-text-secondary">{bindingsText}</div>
          <div className="mt-2 flex items-center gap-2 rounded-lg bg-background-section-burn px-2 py-1 text-xs text-text-tertiary">
            <span className="truncate">{bot.callback_url}</span>
            <button type="button" className="shrink-0 text-text-accent" onClick={handleCopy}>复制</button>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
          <Button onClick={() => onEdit(bot)}>
            <span className="mr-1 i-ri-edit-line size-4" />
            编辑
          </Button>
          <Button onClick={() => setShowDeleteConfirm(true)}>
            <span className="mr-1 i-ri-delete-bin-line size-4" />
            删除
          </Button>
        </div>
      </div>
      <AlertDialog open={showDeleteConfirm} onOpenChange={open => !open && setShowDeleteConfirm(false)}>
        <AlertDialogContent backdropProps={{ forceRender: true }}>
          <div className="flex flex-col gap-2 px-6 pt-6 pb-4">
            <AlertDialogTitle className="w-full truncate title-2xl-semi-bold text-text-primary">
              删除“
              {bot.name}
              ”？
            </AlertDialogTitle>
          </div>
          <AlertDialogActions>
            <AlertDialogCancelButton>取消</AlertDialogCancelButton>
            <AlertDialogConfirmButton disabled={deleteMutation.isPending} onClick={handleDelete}>删除</AlertDialogConfirmButton>
          </AlertDialogActions>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
