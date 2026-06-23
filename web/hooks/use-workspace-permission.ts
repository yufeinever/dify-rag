import type { WorkspacePermission, WorkspacePermissionMode } from '@/utils/workspace-permissions'
import { useCallback, useMemo } from 'react'
import { useAppContext } from '@/context/app-context'
import { canAllWorkspacePermissions, canAnyWorkspacePermission, checkWorkspacePermissions } from '@/utils/workspace-permissions'

export const useWorkspacePermission = () => {
  const { can, workspacePermissions } = useAppContext()

  return useCallback((permission: WorkspacePermission, fallback = false) => {
    return can?.(permission) ?? workspacePermissions?.[permission] ?? fallback
  }, [can, workspacePermissions])
}

export const useWorkspacePermissions = () => {
  const {
    can,
    canAny,
    canAll,
    checkPermissions,
    workspacePermissions,
    workspaceRoleProfile,
  } = useAppContext()

  const canPermission = useCallback((permission: WorkspacePermission, fallback = false) => {
    return can?.(permission) ?? workspacePermissions?.[permission] ?? fallback
  }, [can, workspacePermissions])

  const canAnyPermission = useCallback((permissions: WorkspacePermission[], fallback = false) => {
    if (canAny)
      return canAny(permissions)
    if (can?.any)
      return can.any(permissions)
    if (workspacePermissions)
      return canAnyWorkspacePermission(workspacePermissions, permissions)
    return fallback
  }, [can, canAny, workspacePermissions])

  const canAllPermissions = useCallback((permissions: WorkspacePermission[], fallback = false) => {
    if (canAll)
      return canAll(permissions)
    if (can?.all)
      return can.all(permissions)
    if (workspacePermissions)
      return canAllWorkspacePermissions(workspacePermissions, permissions)
    return fallback
  }, [can, canAll, workspacePermissions])

  const check = useCallback((permissions: WorkspacePermission[], mode: WorkspacePermissionMode = 'all') => {
    if (checkPermissions)
      return checkPermissions(permissions, mode)
    if (can?.check)
      return can.check(permissions, mode)
    if (workspacePermissions)
      return checkWorkspacePermissions(workspacePermissions, permissions, mode)
    return {
      allowed: false,
      mode,
      requested: permissions,
      granted: [],
      missing: permissions,
    }
  }, [can, checkPermissions, workspacePermissions])

  return useMemo(() => ({
    can: canPermission,
    canAny: canAnyPermission,
    canAll: canAllPermissions,
    check,
    permissions: workspacePermissions,
    roleProfile: workspaceRoleProfile,
  }), [canAllPermissions, canAnyPermission, canPermission, check, workspacePermissions, workspaceRoleProfile])
}
