import {
  buildWorkspacePermissions,
  canAllWorkspacePermissions,
  canAnyWorkspacePermission,
  checkWorkspacePermissions,
  createWorkspacePermissionChecker,
  enterpriseWorkspacePermissionPolicy,
  getWorkspaceRoleProfile,
  hasWorkspacePermission,
  workspacePermissionKeys,
  workspacePermissionMetadata,
  workspacePermissionRoles,
} from './workspace-permissions'

describe('workspace-permissions', () => {
  it('maps owner to full workspace administration permissions', () => {
    const permissions = buildWorkspacePermissions('owner')

    expect(permissions['workspace.update']).toBe(true)
    expect(permissions['workspace.member.manage']).toBe(true)
    expect(permissions['workspace.owner.transfer']).toBe(true)
    expect(permissions['workspace.compliance.manage']).toBe(true)
  })

  it('maps admin to manager permissions without owner-only actions', () => {
    const permissions = buildWorkspacePermissions('admin')

    expect(permissions['workspace.member.manage']).toBe(true)
    expect(permissions['model-provider.manage']).toBe(true)
    expect(permissions['workspace.owner.transfer']).toBe(false)
    expect(permissions['workspace.update']).toBe(false)
  })

  it('maps editor to app and dataset edit permissions without admin settings', () => {
    const permissions = buildWorkspacePermissions('editor')

    expect(permissions['app.edit']).toBe(true)
    expect(permissions['dataset.edit']).toBe(true)
    expect(permissions['workspace.member.manage']).toBe(false)
    expect(permissions['model-provider.manage']).toBe(false)
  })

  it('maps dataset operator to dataset permissions only', () => {
    const permissions = buildWorkspacePermissions('dataset_operator')

    expect(permissions['dataset.view']).toBe(true)
    expect(permissions['dataset.create']).toBe(true)
    expect(permissions['app.view']).toBe(false)
    expect(permissions['explore.view']).toBe(false)
  })

  it('keeps normal users read-only outside datasets and settings', () => {
    const permissions = buildWorkspacePermissions('normal')

    expect(permissions['app.view']).toBe(true)
    expect(permissions['tools.view']).toBe(true)
    expect(permissions['app.edit']).toBe(false)
    expect(permissions['dataset.view']).toBe(false)
  })

  it('checks individual, any, and all permissions', () => {
    const permissions = buildWorkspacePermissions('admin')

    expect(hasWorkspacePermission('admin', 'workspace.member.manage')).toBe(true)
    expect(canAnyWorkspacePermission(permissions, ['workspace.owner.transfer', 'model-provider.manage'])).toBe(true)
    expect(canAllWorkspacePermissions(permissions, ['workspace.member.manage', 'model-provider.manage'])).toBe(true)
    expect(canAllWorkspacePermissions(permissions, ['workspace.member.manage', 'workspace.owner.transfer'])).toBe(false)
  })

  it('creates a stable permission checker from a permission map', () => {
    const can = createWorkspacePermissionChecker(buildWorkspacePermissions('editor'))

    expect(can('app.edit')).toBe(true)
    expect(can('workspace.member.manage')).toBe(false)
    expect(can.any(['workspace.member.manage', 'app.edit'])).toBe(true)
    expect(can.all(['app.edit', 'dataset.edit'])).toBe(true)
  })

  it('returns enterprise check details for missing permissions', () => {
    const result = checkWorkspacePermissions(
      buildWorkspacePermissions('editor'),
      ['app.edit', 'workspace.billing.manage'],
    )

    expect(result.allowed).toBe(false)
    expect(result.granted).toEqual(['app.edit'])
    expect(result.missing).toEqual(['workspace.billing.manage'])
  })

  it('supports any-mode enterprise checks', () => {
    const result = checkWorkspacePermissions(
      buildWorkspacePermissions('normal'),
      ['dataset.view', 'app.view'],
      'any',
    )

    expect(result.allowed).toBe(true)
    expect(result.granted).toEqual(['app.view'])
    expect(result.missing).toEqual(['dataset.view'])
  })

  it('keeps B+ permission metadata aligned with permission keys', () => {
    expect(Object.keys(workspacePermissionMetadata).sort()).toEqual([...workspacePermissionKeys].sort())
    expect(workspacePermissionMetadata['workspace.owner.transfer'].risk).toBe('critical')
    expect(workspacePermissionMetadata['dataset.view'].scope).toBe('dataset')
  })

  it('describes role profiles for audits and admin UI', () => {
    const profile = getWorkspaceRoleProfile('admin')

    expect(profile.label).toBe('Admin')
    expect(profile.permissions).toContain('workspace.member.manage')
    expect(profile.permissions).not.toContain('workspace.owner.transfer')
  })

  it('exposes a versioned enterprise permission policy', () => {
    expect(enterpriseWorkspacePermissionPolicy.version).toBe('b-plus-2026-06')
    expect(enterpriseWorkspacePermissionPolicy.defaultMode).toBe('all')
  })

  it('matches the B+ enterprise role permission matrix', () => {
    const expectations = {
      owner: workspacePermissionKeys,
      admin: [
        'workspace.view',
        'workspace.member.view',
        'workspace.member.manage',
        'workspace.billing.manage',
        'workspace.brand.manage',
        'app.view',
        'app.create',
        'app.edit',
        'app.delete',
        'app.publish',
        'app.access-control.manage',
        'app.api-key.manage',
        'dataset.view',
        'dataset.create',
        'dataset.edit',
        'dataset.delete',
        'dataset.member-permission.manage',
        'model-provider.manage',
        'tool-provider.manage',
        'plugin.view',
        'plugin.manage',
        'explore.view',
        'tools.view',
      ],
      editor: [
        'workspace.view',
        'app.view',
        'app.create',
        'app.edit',
        'app.delete',
        'app.publish',
        'app.access-control.manage',
        'dataset.view',
        'dataset.create',
        'dataset.edit',
        'dataset.delete',
        'dataset.member-permission.manage',
        'plugin.view',
        'explore.view',
        'tools.view',
      ],
      dataset_operator: [
        'workspace.view',
        'dataset.view',
        'dataset.create',
        'dataset.edit',
      ],
      normal: [
        'workspace.view',
        'app.view',
        'plugin.view',
        'explore.view',
        'tools.view',
      ],
    } as const

    Object.entries(expectations).forEach(([role, allowedPermissions]) => {
      const permissions = buildWorkspacePermissions(role as keyof typeof expectations)
      const allowed = workspacePermissionKeys.filter(permission => permissions[permission])

      expect(allowed).toEqual(allowedPermissions)
    })
  })

  it('keeps critical and high-risk permissions out of low-privilege roles', () => {
    const lowPrivilegeRoles = ['editor', 'dataset_operator', 'normal'] as const
    const restrictedPermissions = workspacePermissionKeys.filter((permission) => {
      const metadata = workspacePermissionMetadata[permission]
      return metadata.scope === 'workspace' && ['high', 'critical'].includes(metadata.risk)
    })

    lowPrivilegeRoles.forEach((role) => {
      const permissions = buildWorkspacePermissions(role)
      restrictedPermissions.forEach((permission) => {
        expect(permissions[permission]).toBe(false)
      })
    })
  })

  it('keeps permission role lists free of unknown roles', () => {
    const validRoles = ['owner', 'admin', 'editor', 'dataset_operator', 'normal']

    Object.values(workspacePermissionRoles).forEach((roles) => {
      roles.forEach((role) => {
        expect(validRoles).toContain(role)
      })
    })
  })
})
