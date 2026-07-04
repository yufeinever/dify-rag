import type { ChannelIntegrationBot } from '@/service/channel-integrations'
import { Button } from '@langgenius/dify-ui/button'
import { useState } from 'react'
import { useChannelIntegrationBots } from '@/service/channel-integrations'
import { BotItem } from './bot-item'
import { BotModal } from './bot-modal'

type DialogState = {
  mode: 'create'
} | {
  mode: 'edit'
  bot: ChannelIntegrationBot
} | null

export default function ChannelIntegrationsPage() {
  const { data: bots = [], isPending } = useChannelIntegrationBots()
  const [dialogState, setDialogState] = useState<DialogState>(null)

  return (
    <div>
      {!isPending && !bots.length && (
        <div className="mb-4 rounded-xl border border-dashed border-divider-subtle bg-background-section-burn px-5 py-10 text-center">
          <div className="mx-auto mb-3 flex size-11 items-center justify-center rounded-xl bg-components-input-bg-normal text-text-tertiary">
            <span className="i-ri-webhook-line size-6" />
          </div>
          <div className="system-md-semibold text-text-primary">还没有渠道 Bot</div>
          <div className="mt-1 text-sm text-text-tertiary">创建飞书 Bot 后，复制回调地址到飞书开放平台即可接入。</div>
        </div>
      )}
      {!isPending && bots.map(bot => (
        <BotItem key={bot.id} bot={bot} onEdit={bot => setDialogState({ mode: 'edit', bot })} />
      ))}
      <Button variant="secondary" className="w-full" onClick={() => setDialogState({ mode: 'create' })}>
        <span className="mr-1 i-ri-add-line size-4" aria-hidden="true" />
        新增飞书 Bot
      </Button>
      {dialogState?.mode === 'create' && (
        <BotModal open onOpenChange={open => !open && setDialogState(null)} onSaved={() => setDialogState(null)} />
      )}
      {dialogState?.mode === 'edit' && (
        <BotModal open bot={dialogState.bot} onOpenChange={open => !open && setDialogState(null)} onSaved={() => setDialogState(null)} />
      )}
    </div>
  )
}
