import type { DocumentOfficePreviewConfigResponse } from './datasets'
import type { CommonResponse } from '@/models/common'
import { del, get } from './base'

export type GeneratedFile = {
  id: string
  name: string
  mime_type: string
  file_type: string
  extension: string
  size: number
  created_at: number | null
  source_app_id?: string | null
  source_app_name?: string | null
  source_conversation_id?: string | null
  source_message_id?: string | null
  owner_user_id: string
  owner_name: string
  preview_kind: 'native' | 'converted_pdf' | 'unsupported'
  preview_url: string
  download_url: string
}

export type GeneratedFileFacet = {
  id: string
  name: string
  count: number
}

export type GeneratedFileListResponse = {
  data: GeneratedFile[]
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
    accounts: GeneratedFileFacet[]
    apps: GeneratedFileFacet[]
  }
}

export type GeneratedFileListParams = {
  page?: number
  limit?: number
  keyword?: string
  file_type?: string
  source_app_id?: string
  source_app_ids?: string
  owner_user_ids?: string
  include_all?: boolean
  sort?: string
}

export const fetchGeneratedFiles = (params: GeneratedFileListParams): Promise<GeneratedFileListResponse> => {
  return get<GeneratedFileListResponse>('/generated-files', { params })
}

export const fetchGeneratedFilePreviewConfig = (fileId: string): Promise<DocumentOfficePreviewConfigResponse> => {
  return get<DocumentOfficePreviewConfigResponse>(`/generated-files/${fileId}`, {})
}

export const fetchGeneratedFileDownloadUrl = (fileId: string): Promise<{ url: string }> => {
  return get<{ url: string }>(`/generated-files/${fileId}/download-url`, {})
}

export const deleteGeneratedFile = (fileId: string): Promise<CommonResponse> => {
  return del<CommonResponse>(`/generated-files/${fileId}`)
}
