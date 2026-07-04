import type { ChannelIntegrationBot, ChannelIntegrationBotPayload, ChannelIntegrationPurpose } from '@/service/channel-integrations'
import { Button } from '@langgenius/dify-ui/button'
import { Dialog, DialogCloseButton, DialogContent, DialogTitle } from '@langgenius/dify-ui/dialog'
import { FieldControl, FieldLabel, FieldRoot } from '@langgenius/dify-ui/field'
import { toast } from '@langgenius/dify-ui/toast'
import { useMemo, useState } from 'react'
import { useChannelIntegrationApps, useCreateChannelIntegrationBot, useUpdateChannelIntegrationBot } from '@/service/channel-integrations'

const HIDDEN_VALUE = '[__HIDDEN__]'

const purposeMeta: Record<ChannelIntegrationPurpose, { label: string, description: string }> = {
  default: {
    label: '主入口应用（必选）',
    description: '所有普通消息默认进入这个 Dify 应用，由它自行识别意图并调用能力。',
  },
  copywriting: {
    label: '文案专项覆盖（可选）',
    description: '配置后，命中文案关键词的消息会改发到这个应用；不配置则交给主入口应用。',
  },
  poster: {
    label: '海报专项覆盖（可选）',
    description: '配置后，命中海报关键词的消息会由网关走异步海报生成并回传飞书图片；不配置则交给主入口应用。',
  },
}

const requiredPurposes: ChannelIntegrationPurpose[] = ['default']
const optionalPurposes: ChannelIntegrationPurpose[] = ['copywriting', 'poster']
const purposes: ChannelIntegrationPurpose[] = [...requiredPurposes, ...optionalPurposes]

type BotModalProps = {
  open: boolean
  bot?: ChannelIntegrationBot | null
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

const getInitialBindings = (bot?: ChannelIntegrationBot | null): Record<ChannelIntegrationPurpose, string> => {
  const next = { default: '', copywriting: '', poster: '' }
  bot?.bindings.forEach((binding) => {
    next[binding.purpose] = binding.app_id
  })
  return next
}

export function BotModal({ open, bot, onOpenChange, onSaved }: BotModalProps) {
  const { data: appsData } = useChannelIntegrationApps()
  const createMutation = useCreateChannelIntegrationBot()
  const updateMutation = useUpdateChannelIntegrationBot()
  const editing = !!bot
  const [name, setName] = useState(bot?.name ?? '')
  const [enabled, setEnabled] = useState(bot?.enabled ?? true)
  const [appId, setAppId] = useState(bot?.app_id ?? '')
  const [appSecret, setAppSecret] = useState(editing ? HIDDEN_VALUE : '')
  const [verificationToken, setVerificationToken] = useState(editing ? HIDDEN_VALUE : '')
  const [encryptKey, setEncryptKey] = useState(editing ? HIDDEN_VALUE : '')
  const [botName, setBotName] = useState(bot?.bot_name ?? 'MMBAI')
  const [botOpenId, setBotOpenId] = useState(bot?.bot_open_id ?? '')
  const [bindings, setBindings] = useState<Record<ChannelIntegrationPurpose, string>>(() => getInitialBindings(bot))

  const isSaving = createMutation.isPending || updateMutation.isPending
  const canSubmit = name.trim() && appId.trim() && appSecret && verificationToken && encryptKey && bindings.default

  const handleSubmit = () => {
    const body: ChannelIntegrationBotPayload = {
      name: name.trim(),
      channel: 'feishu',
      enabled,
      app_id: appId.trim(),
      app_secret: appSecret,
      verification_token: verificationToken,
      encrypt_key: encryptKey,
      bot_name: botName.trim() || null,
      bot_open_id: botOpenId.trim() || null,
      bindings: purposes
        .filter(purpose => bindings[purpose])
        .map(purpose => ({ purpose, app_id: bindings[purpose] })),
    }
    const options = {
      onSuccess: () => {
        toast.success(editing ? '飞书 Bot 已更新' : '飞书 Bot 已创建')
        onSaved()
      },
    }
    if (bot)
      updateMutation.mutate({ id: bot.id, body }, options)
    else
      createMutation.mutate(body, options)
  }

  const appOptions = useMemo(() => {
    return (appsData?.data ?? []).map(app => ({ value: app.id, label: app.name }))
  }, [appsData?.data])

  return (
    <Dialog open={open} onOpenChange={onOpenChange} disablePointerDismissal>
      <DialogContent backdropProps={{ forceRender: true }} className="w-[720px] border-none p-8 pb-6 text-left">
        <DialogCloseButton />
        <DialogTitle className="mb-6 pr-8 text-xl font-semibold text-text-primary">
          {editing ? '编辑飞书 Bot' : '新增飞书 Bot'}
        </DialogTitle>
        <div className="grid grid-cols-2 gap-4">
          <FieldRoot name="name">
            <FieldLabel>Bot 名称</FieldLabel>
            <FieldControl required value={name} onChange={e => setName(e.target.value)} placeholder="例如：MMBAI 飞书助手" />
          </FieldRoot>
          <FieldRoot name="enabled">
            <FieldLabel>状态</FieldLabel>
            <label className="flex h-9 items-center gap-2 text-sm text-text-secondary">
              <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
              启用这个 Bot
            </label>
          </FieldRoot>
          <FieldRoot name="app_id">
            <FieldLabel>飞书 APP_ID</FieldLabel>
            <FieldControl required value={appId} onChange={e => setAppId(e.target.value)} placeholder="cli_xxx" />
          </FieldRoot>
          <FieldRoot name="bot_name">
            <FieldLabel>Bot 名称 / @名称</FieldLabel>
            <FieldControl value={botName} onChange={e => setBotName(e.target.value)} placeholder="MMBAI" />
          </FieldRoot>
          <FieldRoot name="app_secret">
            <FieldLabel>APP_SECRET</FieldLabel>
            <FieldControl required type="password" value={appSecret} onChange={e => setAppSecret(e.target.value)} />
          </FieldRoot>
          <FieldRoot name="verification_token">
            <FieldLabel>Verification Token</FieldLabel>
            <FieldControl required type="password" value={verificationToken} onChange={e => setVerificationToken(e.target.value)} />
          </FieldRoot>
          <FieldRoot name="encrypt_key">
            <FieldLabel>Encrypt Key</FieldLabel>
            <FieldControl required type="password" value={encryptKey} onChange={e => setEncryptKey(e.target.value)} />
          </FieldRoot>
          <FieldRoot name="bot_open_id">
            <FieldLabel>Bot Open ID（可选）</FieldLabel>
            <FieldControl value={botOpenId} onChange={e => setBotOpenId(e.target.value)} placeholder="用于更严格的群聊 @ 判断" />
          </FieldRoot>
        </div>
        <div className="mt-6 rounded-lg border border-divider-subtle bg-background-section-burn p-4">
          <div className="system-sm-semibold text-text-primary">消息入口与专项覆盖</div>
          <div className="mt-1 text-xs text-text-tertiary">
            不配置专项覆盖时，所有消息都会交给主入口应用，由 Dify 应用自行识别和调用能力。
          </div>
          <div className="grid gap-3">
            {purposes.map(purpose => (
              <label key={purpose} className="grid grid-cols-[170px_1fr] items-start gap-3 text-sm first:mt-4">
                <span className="pt-2 text-text-secondary">
                  <span className="block text-text-primary">{purposeMeta[purpose].label}</span>
                  <span className="mt-0.5 block text-xs leading-4 text-text-tertiary">{purposeMeta[purpose].description}</span>
                </span>
                <select
                  className="h-9 rounded-lg border bg-components-input-bg-normal px-3 text-sm outline-none"
                  value={bindings[purpose]}
                  onChange={e => setBindings(prev => ({ ...prev, [purpose]: e.target.value }))}
                  required={purpose === 'default'}
                >
                  <option value="">{purpose === 'default' ? '请选择主入口应用' : '不启用覆盖'}</option>
                  {appOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
            ))}
          </div>
        </div>
        <div className="mt-6 flex items-center justify-end gap-2">
          <Button type="button" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button type="button" variant="primary" disabled={!canSubmit || isSaving} onClick={handleSubmit}>
            保存
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
