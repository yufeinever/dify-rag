'use client'

import type { ICurrentWorkspace, LangGeniusVersionResponse, UserProfileResponse } from '@/models/common'
import type {
  WorkspacePermission,
  WorkspacePermissionChecker,
  WorkspacePermissionCheckResult,
  WorkspacePermissionMap,
  WorkspacePermissionMode,
  WorkspaceRoleProfile,
} from '@/utils/workspace-permissions'
import { noop } from 'es-toolkit/function'
import { createContext, useContext, useContextSelector } from 'use-context-selector'
import { buildWorkspacePermissions } from '@/utils/workspace-permissions'

export type AppContextValue = {
  userProfile: UserProfileResponse
  mutateUserProfile: VoidFunction
  currentWorkspace: ICurrentWorkspace
  isCurrentWorkspaceManager: boolean
  isCurrentWorkspaceOwner: boolean
  isCurrentWorkspaceEditor: boolean
  isCurrentWorkspaceDatasetOperator: boolean
  workspacePermissions?: WorkspacePermissionMap
  workspaceRoleProfile?: WorkspaceRoleProfile
  can?: WorkspacePermissionChecker
  canAny?: (permissions: WorkspacePermission[]) => boolean
  canAll?: (permissions: WorkspacePermission[]) => boolean
  checkPermissions?: (permissions: WorkspacePermission[], mode?: WorkspacePermissionMode) => WorkspacePermissionCheckResult
  mutateCurrentWorkspace: VoidFunction
  langGeniusVersionInfo: LangGeniusVersionResponse
  useSelector: typeof useSelector
  isLoadingCurrentWorkspace: boolean
  isValidatingCurrentWorkspace: boolean
}

export const userProfilePlaceholder = {
  id: '',
  name: '',
  email: '',
  avatar: '',
  avatar_url: '',
  is_password_set: false,
}

export const initialLangGeniusVersionInfo = {
  current_env: '',
  current_version: '',
  latest_version: '',
  release_date: '',
  release_notes: '',
  version: '',
  can_auto_update: false,
}

export const initialWorkspaceInfo: ICurrentWorkspace = {
  id: '',
  name: '',
  plan: '',
  status: '',
  created_at: 0,
  role: 'normal',
  providers: [],
  trial_credits: 200,
  trial_credits_used: 0,
  next_credit_reset_date: 0,
}

export const initialWorkspacePermissions = buildWorkspacePermissions(initialWorkspaceInfo.role)

export const AppContext = createContext<AppContextValue>({
  userProfile: userProfilePlaceholder,
  currentWorkspace: initialWorkspaceInfo,
  isCurrentWorkspaceManager: false,
  isCurrentWorkspaceOwner: false,
  isCurrentWorkspaceEditor: false,
  isCurrentWorkspaceDatasetOperator: false,
  workspacePermissions: initialWorkspacePermissions,
  can: Object.assign(() => false, {
    any: () => false,
    all: () => false,
    check: (permissions: WorkspacePermission[], mode: WorkspacePermissionMode = 'all') => ({
      allowed: false,
      mode,
      requested: permissions,
      granted: [],
      missing: permissions,
    }),
  }),
  canAny: () => false,
  canAll: () => false,
  checkPermissions: (permissions: WorkspacePermission[], mode: WorkspacePermissionMode = 'all') => ({
    allowed: false,
    mode,
    requested: permissions,
    granted: [],
    missing: permissions,
  }),
  mutateUserProfile: noop,
  mutateCurrentWorkspace: noop,
  langGeniusVersionInfo: initialLangGeniusVersionInfo,
  useSelector,
  isLoadingCurrentWorkspace: false,
  isValidatingCurrentWorkspace: false,
})

export function useSelector<T>(selector: (value: AppContextValue) => T): T {
  return useContextSelector(AppContext, selector)
}

export const useAppContext = () => useContext(AppContext)
