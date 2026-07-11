import type { CommonResponse } from '@/models/common'
import { del, get } from './base'

export type GeneratedAsset = {
  id: string
  name: string
  mime_type: string
  file_type: string
  extension?: string
  size: number
  created_at: number | null
  source_app_id?: string | null
  source_app_name?: string | null
  source_conversation_id?: string | null
  source_message_id?: string | null
  owner_user_id: string
  owner_name: string | null
  preview_kind: 'native' | 'converted_pdf' | 'unsupported' | 'unavailable'
  preview_url: string
  download_url: string
  storage_type?: 'tool_file' | 'remote_url' | string
  source_url?: string | null
  thumbnail_url?: string | null
  source_workflow_run_id?: string | null
  source_kind?: 'message_file' | 'tool_file' | 'workflow_video' | 'workflow_poster' | 'ppt_artifact' | string | null
  asset_metadata?: Record<string, unknown> | null
}

export type GeneratedAssetFacet = {
  id: string
  name: string
  count: number
}

export type GeneratedAssetListResponse = {
  data: GeneratedAsset[]
  page: number
  limit: number
  total: number
  has_more: boolean
  stats: {
    total: number
    total_size: number
    by_type: Record<string, number>
  }
  facets?: {
    accounts: GeneratedAssetFacet[]
    apps: GeneratedAssetFacet[]
    file_types?: GeneratedAssetFacet[]
    source_kinds?: GeneratedAssetFacet[]
  }
}

export type GeneratedAssetListParams = {
  page?: number
  limit?: number
  keyword?: string
  file_type?: string
  source_app_id?: string
  source_app_ids?: string
  owner_user_ids?: string
  include_all?: boolean
  sort?: string
  source_kind?: string
  storage_type?: string
  created_after?: number
  created_before?: number
}

export type GeneratedAssetPreviewConfigResponse = GeneratedAsset & {
  mode: 'native' | 'remote' | 'unavailable'
  original_file_type: string
}

export const fetchGeneratedAssets = (params: GeneratedAssetListParams): Promise<GeneratedAssetListResponse> => {
  return get<GeneratedAssetListResponse>('/generated-assets', { params })
}

export const fetchGeneratedAssetPreviewConfig = (assetId: string): Promise<GeneratedAssetPreviewConfigResponse> => {
  return get<GeneratedAssetPreviewConfigResponse>(`/generated-assets/${assetId}`, {})
}

export const fetchGeneratedAssetDownloadUrl = (assetId: string): Promise<{ url: string }> => {
  return get<{ url: string }>(`/generated-assets/${assetId}/download-url`, {})
}

export const deleteGeneratedAsset = (assetId: string): Promise<CommonResponse> => {
  return del<CommonResponse>(`/generated-assets/${assetId}`)
}
