'use client'

import type { ReactNode } from 'react'
import type { WorkspacePermission, WorkspacePermissionMode } from '@/utils/workspace-permissions'
import { useWorkspacePermissions } from '@/hooks/use-workspace-permission'

type WorkspacePermissionGuardProps = {
  permission?: WorkspacePermission
  permissions?: WorkspacePermission[]
  mode?: WorkspacePermissionMode
  fallback?: ReactNode
  children: ReactNode
}

const normalizePermissions = (
  permission?: WorkspacePermission,
  permissions?: WorkspacePermission[],
) => {
  if (permissions?.length)
    return permissions
  if (permission)
    return [permission]
  return []
}

export const WorkspacePermissionGuard = ({
  permission,
  permissions,
  mode = 'all',
  fallback = null,
  children,
}: WorkspacePermissionGuardProps) => {
  const { check } = useWorkspacePermissions()
  const requestedPermissions = normalizePermissions(permission, permissions)

  if (requestedPermissions.length === 0)
    return <>{children}</>

  const result = check(requestedPermissions, mode)

  if (!result.allowed)
    return <>{fallback}</>

  return <>{children}</>
}

export default WorkspacePermissionGuard
