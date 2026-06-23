import type { ICurrentWorkspace } from '@/models/common'

export type WorkspaceRole = ICurrentWorkspace['role']
export type WorkspacePermissionScope = 'workspace' | 'app' | 'dataset' | 'provider' | 'plugin' | 'navigation'
export type WorkspacePermissionEffect = 'read' | 'create' | 'update' | 'delete' | 'publish' | 'manage'
export type WorkspacePermissionRisk = 'low' | 'medium' | 'high' | 'critical'
export type WorkspacePermissionMode = 'all' | 'any'

export const workspacePermissionRoles = {
  'workspace.view': ['owner', 'admin', 'editor', 'dataset_operator', 'normal'],
  'workspace.update': ['owner'],
  'workspace.member.view': ['owner', 'admin'],
  'workspace.member.manage': ['owner', 'admin'],
  'workspace.owner.transfer': ['owner'],
  'workspace.billing.manage': ['owner', 'admin'],
  'workspace.compliance.manage': ['owner'],
  'workspace.brand.manage': ['owner', 'admin'],
  'app.view': ['owner', 'admin', 'editor', 'normal'],
  'app.create': ['owner', 'admin', 'editor'],
  'app.edit': ['owner', 'admin', 'editor'],
  'app.delete': ['owner', 'admin', 'editor'],
  'app.publish': ['owner', 'admin', 'editor'],
  'app.access-control.manage': ['owner', 'admin', 'editor'],
  'app.api-key.manage': ['owner', 'admin'],
  'dataset.view': ['owner', 'admin', 'editor', 'dataset_operator'],
  'dataset.create': ['owner', 'admin', 'editor', 'dataset_operator'],
  'dataset.edit': ['owner', 'admin', 'editor', 'dataset_operator'],
  'dataset.delete': ['owner', 'admin', 'editor'],
  'dataset.member-permission.manage': ['owner', 'admin', 'editor'],
  'model-provider.manage': ['owner', 'admin'],
  'tool-provider.manage': ['owner', 'admin'],
  'plugin.view': ['owner', 'admin', 'editor', 'normal'],
  'plugin.manage': ['owner', 'admin'],
  'explore.view': ['owner', 'admin', 'editor', 'normal'],
  'tools.view': ['owner', 'admin', 'editor', 'normal'],
} as const satisfies Record<string, readonly WorkspaceRole[]>

export type WorkspacePermission = keyof typeof workspacePermissionRoles
export type WorkspacePermissionMap = Record<WorkspacePermission, boolean>

export type WorkspacePermissionMetadata = {
  scope: WorkspacePermissionScope
  effect: WorkspacePermissionEffect
  risk: WorkspacePermissionRisk
  label: string
}

export type WorkspacePermissionCheckResult = {
  allowed: boolean
  mode: WorkspacePermissionMode
  requested: WorkspacePermission[]
  granted: WorkspacePermission[]
  missing: WorkspacePermission[]
}

export type WorkspaceRoleProfile = {
  role: WorkspaceRole
  label: string
  description: string
  permissions: WorkspacePermission[]
}

export type WorkspacePermissionChecker = ((permission: WorkspacePermission) => boolean) & {
  any: (requestedPermissions: WorkspacePermission[]) => boolean
  all: (requestedPermissions: WorkspacePermission[]) => boolean
  check: (requestedPermissions: WorkspacePermission[], mode?: WorkspacePermissionMode) => WorkspacePermissionCheckResult
}

export const workspacePermissionKeys = Object.keys(workspacePermissionRoles) as WorkspacePermission[]

export const workspaceRoleLabels = {
  owner: 'Owner',
  admin: 'Admin',
  editor: 'Editor',
  dataset_operator: 'Dataset operator',
  normal: 'Normal member',
} as const satisfies Record<WorkspaceRole, string>

export const workspaceRoleDescriptions = {
  owner: 'Full workspace control including ownership transfer and compliance settings.',
  admin: 'Workspace administration without owner-only controls.',
  editor: 'App and dataset creation and editing without workspace administration.',
  dataset_operator: 'Dataset-focused work without app access.',
  normal: 'Read access to apps, tools, plugins, and explore surfaces.',
} as const satisfies Record<WorkspaceRole, string>

export const workspacePermissionMetadata = {
  'workspace.view': { scope: 'workspace', effect: 'read', risk: 'low', label: 'View workspace' },
  'workspace.update': { scope: 'workspace', effect: 'update', risk: 'high', label: 'Update workspace' },
  'workspace.member.view': { scope: 'workspace', effect: 'read', risk: 'medium', label: 'View workspace members' },
  'workspace.member.manage': { scope: 'workspace', effect: 'manage', risk: 'high', label: 'Manage workspace members' },
  'workspace.owner.transfer': { scope: 'workspace', effect: 'manage', risk: 'critical', label: 'Transfer workspace ownership' },
  'workspace.billing.manage': { scope: 'workspace', effect: 'manage', risk: 'high', label: 'Manage billing' },
  'workspace.compliance.manage': { scope: 'workspace', effect: 'manage', risk: 'critical', label: 'Manage compliance settings' },
  'workspace.brand.manage': { scope: 'workspace', effect: 'manage', risk: 'medium', label: 'Manage workspace brand' },
  'app.view': { scope: 'app', effect: 'read', risk: 'low', label: 'View apps' },
  'app.create': { scope: 'app', effect: 'create', risk: 'medium', label: 'Create apps' },
  'app.edit': { scope: 'app', effect: 'update', risk: 'medium', label: 'Edit apps' },
  'app.delete': { scope: 'app', effect: 'delete', risk: 'high', label: 'Delete apps' },
  'app.publish': { scope: 'app', effect: 'publish', risk: 'medium', label: 'Publish apps' },
  'app.access-control.manage': { scope: 'app', effect: 'manage', risk: 'high', label: 'Manage app access control' },
  'app.api-key.manage': { scope: 'app', effect: 'manage', risk: 'high', label: 'Manage app API keys' },
  'dataset.view': { scope: 'dataset', effect: 'read', risk: 'low', label: 'View datasets' },
  'dataset.create': { scope: 'dataset', effect: 'create', risk: 'medium', label: 'Create datasets' },
  'dataset.edit': { scope: 'dataset', effect: 'update', risk: 'medium', label: 'Edit datasets' },
  'dataset.delete': { scope: 'dataset', effect: 'delete', risk: 'high', label: 'Delete datasets' },
  'dataset.member-permission.manage': { scope: 'dataset', effect: 'manage', risk: 'high', label: 'Manage dataset member permissions' },
  'model-provider.manage': { scope: 'provider', effect: 'manage', risk: 'high', label: 'Manage model providers' },
  'tool-provider.manage': { scope: 'provider', effect: 'manage', risk: 'high', label: 'Manage tool providers' },
  'plugin.view': { scope: 'plugin', effect: 'read', risk: 'low', label: 'View plugins' },
  'plugin.manage': { scope: 'plugin', effect: 'manage', risk: 'high', label: 'Manage plugins' },
  'explore.view': { scope: 'navigation', effect: 'read', risk: 'low', label: 'View explore' },
  'tools.view': { scope: 'navigation', effect: 'read', risk: 'low', label: 'View tools' },
} as const satisfies Record<WorkspacePermission, WorkspacePermissionMetadata>

export const enterpriseWorkspacePermissionPolicy = {
  version: 'b-plus-2026-06',
  defaultMode: 'all',
  permissions: workspacePermissionMetadata,
  roleLabels: workspaceRoleLabels,
} as const

export const hasWorkspacePermission = (role: WorkspaceRole | undefined, permission: WorkspacePermission) => {
  if (!role)
    return false

  return (workspacePermissionRoles[permission] as readonly WorkspaceRole[]).includes(role)
}

export const buildWorkspacePermissions = (role: WorkspaceRole | undefined): WorkspacePermissionMap => {
  return workspacePermissionKeys.reduce((permissions, permission) => {
    permissions[permission] = hasWorkspacePermission(role, permission)
    return permissions
  }, {} as WorkspacePermissionMap)
}

export const canAnyWorkspacePermission = (
  permissions: WorkspacePermissionMap,
  requestedPermissions: WorkspacePermission[],
) => requestedPermissions.some(permission => permissions[permission])

export const canAllWorkspacePermissions = (
  permissions: WorkspacePermissionMap,
  requestedPermissions: WorkspacePermission[],
) => requestedPermissions.every(permission => permissions[permission])

export const checkWorkspacePermissions = (
  permissions: WorkspacePermissionMap,
  requestedPermissions: WorkspacePermission[],
  mode: WorkspacePermissionMode = enterpriseWorkspacePermissionPolicy.defaultMode,
): WorkspacePermissionCheckResult => {
  const granted = requestedPermissions.filter(permission => permissions[permission])
  const missing = requestedPermissions.filter(permission => !permissions[permission])
  const allowed = mode === 'any'
    ? requestedPermissions.length > 0 && granted.length > 0
    : missing.length === 0

  return {
    allowed,
    mode,
    requested: requestedPermissions,
    granted,
    missing,
  }
}

export const getWorkspaceRoleProfile = (role: WorkspaceRole): WorkspaceRoleProfile => {
  return {
    role,
    label: workspaceRoleLabels[role],
    description: workspaceRoleDescriptions[role],
    permissions: workspacePermissionKeys.filter(permission => hasWorkspacePermission(role, permission)),
  }
}

export const createWorkspacePermissionChecker = (permissions: WorkspacePermissionMap): WorkspacePermissionChecker => {
  const checker = ((permission: WorkspacePermission) => permissions[permission]) as WorkspacePermissionChecker
  checker.any = requestedPermissions => canAnyWorkspacePermission(permissions, requestedPermissions)
  checker.all = requestedPermissions => canAllWorkspacePermissions(permissions, requestedPermissions)
  checker.check = (requestedPermissions, mode = enterpriseWorkspacePermissionPolicy.defaultMode) => {
    return checkWorkspacePermissions(permissions, requestedPermissions, mode)
  }

  return checker
}
