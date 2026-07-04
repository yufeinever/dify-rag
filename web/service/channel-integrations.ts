import type { AppListResponse } from '@/models/app'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { del, get, post } from './base'

export type ChannelIntegrationPurpose = 'default' | 'copywriting' | 'poster'

export type ChannelIntegrationBinding = {
  id?: string | null
  purpose: ChannelIntegrationPurpose
  app_id: string
  app_name?: string | null
}

export type ChannelIntegrationBot = {
  id: string
  name: string
  channel: 'feishu'
  enabled: boolean
  app_id: string
  app_secret_configured: boolean
  verification_token_configured: boolean
  encrypt_key_configured: boolean
  bot_name?: string | null
  bot_open_id?: string | null
  callback_url: string
  callback_token: string
  bindings: ChannelIntegrationBinding[]
  last_verified_at?: number | null
  created_at?: number | null
  updated_at?: number | null
}

export type ChannelIntegrationBotPayload = {
  name: string
  channel: 'feishu'
  enabled: boolean
  app_id: string
  app_secret: string
  verification_token: string
  encrypt_key: string
  bot_name?: string | null
  bot_open_id?: string | null
  bindings: Array<{
    purpose: ChannelIntegrationPurpose
    app_id: string
  }>
}

const queryKey = ['channel-integrations', 'bots'] as const
const appsQueryKey = ['channel-integrations', 'apps'] as const

export const useChannelIntegrationBots = () => {
  return useQuery<ChannelIntegrationBot[]>({
    queryKey,
    queryFn: () => get<ChannelIntegrationBot[]>('/workspaces/current/channel-integrations/bots'),
  })
}

export const useChannelIntegrationApps = () => {
  return useQuery<AppListResponse>({
    queryKey: appsQueryKey,
    queryFn: () => get<AppListResponse>('/apps', { params: { page: 1, limit: 100 } }),
  })
}

export const useCreateChannelIntegrationBot = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ChannelIntegrationBotPayload) => post<ChannelIntegrationBot>('/workspaces/current/channel-integrations/bots', { body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })
}

export const useUpdateChannelIntegrationBot = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string, body: ChannelIntegrationBotPayload }) => post<ChannelIntegrationBot>(`/workspaces/current/channel-integrations/bots/${id}`, { body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })
}

export const useDeleteChannelIntegrationBot = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => del(`/workspaces/current/channel-integrations/bots/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })
}
