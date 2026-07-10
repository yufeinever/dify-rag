import type { AppIconType, AppModeEnum } from '@/types/app'

type AppBasicInfo = {
  id: string
  mode: AppModeEnum
  icon_type: AppIconType | null
  icon: string
  icon_background: string
  icon_url: string
  name: string
  description: string
  use_icon_as_answer_icon: boolean
}

export type AppCategory = string

export type App = {
  app: AppBasicInfo
  app_id: string
  description: string
  copyright: string
  privacy_policy: string | null
  custom_disclaimer: string | null
  categories: AppCategory[]
  position: number
  is_listed: boolean
  install_count: number
  installed: boolean
  editable: boolean
  is_agent: boolean
  can_trial: boolean
}

export type InstalledApp = {
  app: AppBasicInfo
  id: string
  uninstallable: boolean
  is_pinned: boolean
}

export type WorkflowRunHistoryItem = {
  id: string
  status: 'running' | 'succeeded' | 'failed' | 'stopped' | 'partial-succeeded' | string
  request: string
  created_at: number
  finished_at: number | null
  elapsed_time: number
  duration: string | null
  aspect_ratio: string | null
  resolution: string | null
  error: string | null
  video_url: string | null
  character_image_url: string | null
  scene_image_url: string | null
}

export type WorkflowRunHistoryDetail = WorkflowRunHistoryItem & {
  inputs: Record<string, unknown>
  outputs: Record<string, unknown>
  result: string
  script: string
  storyboard: string
  title: string | null
  intent: string | null
}

export type WorkflowRunHistoryPage = {
  limit: number
  has_more: boolean
  last_id: string | null
  data: WorkflowRunHistoryItem[]
}
