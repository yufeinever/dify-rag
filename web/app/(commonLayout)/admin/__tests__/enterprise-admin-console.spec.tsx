import type { AppContextValue } from '@/context/app-context'
import type { ProviderContextState } from '@/context/provider-context'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { renderWithSystemFeatures } from '@/__tests__/utils/mock-system-features'
import { useAppContext } from '@/context/app-context'
import { useProviderContext } from '@/context/provider-context'
import { createMember, resetMemberPassword } from '@/service/common'
import { useMembers, useWorkspaces } from '@/service/use-common'
import EnterpriseAdminConsole from '../enterprise-admin-console'

const { mockToastSuccess, mockToastError, mockRefetchMembers } = vi.hoisted(() => ({
  mockToastSuccess: vi.fn(),
  mockToastError: vi.fn(),
  mockRefetchMembers: vi.fn(() => Promise.resolve()),
}))

vi.mock('@langgenius/dify-ui/toast', () => ({
  toast: {
    success: mockToastSuccess,
    error: mockToastError,
  },
}))

vi.mock('@/context/app-context', () => ({
  useAppContext: vi.fn(),
}))

vi.mock('@/context/provider-context', () => ({
  useProviderContext: vi.fn(),
}))

vi.mock('@/service/use-common', () => ({
  useMembers: vi.fn(),
  useWorkspaces: vi.fn(),
}))

vi.mock('@/service/common', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/service/common')>()
  return {
    ...actual,
    createMember: vi.fn(),
    resetMemberPassword: vi.fn(),
    deleteMemberOrCancelInvitation: vi.fn(),
    updateMemberRole: vi.fn(),
  }
})

vi.mock('@/service/apps', () => ({
  applyPermissionTemplate: vi.fn(),
  createPermissionGroup: vi.fn(),
  createPermissionTemplate: vi.fn(),
  deletePermissionGroup: vi.fn(),
  deletePermissionTemplate: vi.fn(),
  fetchAdminAuditLogs: vi.fn(() => Promise.resolve({ data: [] })),
  fetchAppList: vi.fn(() => Promise.resolve({ data: [] })),
  fetchAppPermissionMembers: vi.fn(() => Promise.resolve({ data: [] })),
  fetchExploreAppPermissionMembers: vi.fn(() => Promise.resolve({ data: [] })),
  fetchPermissionGroups: vi.fn(() => Promise.resolve({ data: [] })),
  fetchPermissionTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  fetchWorkspaceUiPolicy: vi.fn(() => Promise.resolve({ show_unauthorized_resource_cards: false })),
  updateAdminUiPolicy: vi.fn(),
  updateAppPermissionMembers: vi.fn(),
  updateExploreAppPermissionMembers: vi.fn(),
  updatePermissionGroup: vi.fn(),
  updatePermissionTemplate: vi.fn(),
}))

vi.mock('@/service/datasets', () => ({
  fetchDatasets: vi.fn(() => Promise.resolve({ data: [] })),
  updateDatasetSetting: vi.fn(),
}))

vi.mock('@/service/explore', () => ({
  fetchInstalledAppList: vi.fn(() => Promise.resolve({ installed_apps: [] })),
}))

const ownerMember = {
  id: 'owner-id',
  name: 'Owner',
  email: 'owner@example.com',
  avatar: '',
  avatar_url: null,
  role: 'owner' as const,
  status: 'active' as const,
  created_at: 1710000000,
  last_active_at: 1710000000,
  last_login_at: 1710000000,
}

const normalMember = {
  id: 'normal-id',
  name: 'Normal User',
  email: 'normal@example.com',
  avatar: '',
  avatar_url: null,
  role: 'normal' as const,
  status: 'active' as const,
  created_at: 1710000000,
  last_active_at: 1710000000,
  last_login_at: 1710000000,
}

const adminMember = {
  id: 'admin-target-id',
  name: 'Admin Target',
  email: 'admin-target@example.com',
  avatar: '',
  avatar_url: null,
  role: 'admin' as const,
  status: 'active' as const,
  created_at: 1710000000,
  last_active_at: 1710000000,
  last_login_at: 1710000000,
}

const baseAppContextValue: AppContextValue = {
  userProfile: {
    id: 'owner-id',
    name: 'Owner',
    email: 'owner@example.com',
    avatar: '',
    avatar_url: '',
    is_password_set: true,
  },
  mutateUserProfile: vi.fn(),
  currentWorkspace: {
    id: 'tenant-id',
    name: 'MMBAI',
    plan: '',
    status: 'normal',
    created_at: 0,
    role: 'owner',
    providers: [],
    trial_credits: 0,
    trial_credits_used: 0,
    next_credit_reset_date: 0,
  },
  isCurrentWorkspaceManager: true,
  isCurrentWorkspaceOwner: true,
  isCurrentWorkspaceEditor: true,
  isCurrentWorkspaceDatasetOperator: false,
  mutateCurrentWorkspace: vi.fn(),
  langGeniusVersionInfo: {
    current_env: 'testing',
    current_version: '0.1.0',
    latest_version: '0.1.0',
    release_date: '',
    release_notes: '',
    version: '0.1.0',
    can_auto_update: false,
  },
  useSelector: vi.fn(),
  isLoadingCurrentWorkspace: false,
  isValidatingCurrentWorkspace: false,
  canAny: vi.fn(() => true),
}

type AppContextOverrides = Partial<Omit<AppContextValue, 'currentWorkspace' | 'userProfile'>> & {
  currentWorkspace?: Partial<AppContextValue['currentWorkspace']>
  userProfile?: Partial<AppContextValue['userProfile']>
}

const renderConsole = (overrides: AppContextOverrides = {}) => {
  vi.mocked(useAppContext).mockReturnValue({
    ...baseAppContextValue,
    ...overrides,
    currentWorkspace: {
      ...baseAppContextValue.currentWorkspace,
      ...overrides.currentWorkspace,
    },
    userProfile: {
      ...baseAppContextValue.userProfile,
      ...overrides.userProfile,
    },
  } as AppContextValue)

  return renderWithSystemFeatures(<EnterpriseAdminConsole />)
}

const openAccountsSection = () => {
  fireEvent.click(screen.getAllByText('账号管理')[0]!)
}

describe('EnterpriseAdminConsole member account management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRefetchMembers.mockResolvedValue(undefined)
    vi.mocked(useProviderContext).mockReturnValue({
      datasetOperatorEnabled: true,
    } as unknown as ProviderContextState)
    vi.mocked(useMembers).mockReturnValue({
      data: { accounts: [ownerMember, normalMember, adminMember] },
      isLoading: false,
      refetch: mockRefetchMembers,
    } as unknown as ReturnType<typeof useMembers>)
    vi.mocked(useWorkspaces).mockReturnValue({
      data: { workspaces: [] },
      isLoading: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useWorkspaces>)
    vi.mocked(createMember).mockResolvedValue({ result: 'success', account: normalMember })
    vi.mocked(resetMemberPassword).mockResolvedValue({ result: 'success' })
  })

  it('should create a member with a password from the account dialog', async () => {
    renderConsole()
    openAccountsSection()

    fireEvent.click(screen.getByText('新增账号'))
    fireEvent.change(screen.getByLabelText('登录邮箱'), { target: { value: 'new.user@example.com' } })
    fireEvent.change(screen.getByLabelText('显示名称'), { target: { value: 'New User' } })
    fireEvent.change(screen.getByLabelText('初始密码'), { target: { value: 'newPassword123' } })
    fireEvent.change(screen.getByLabelText('确认密码'), { target: { value: 'newPassword123' } })
    fireEvent.click(screen.getByText('创建账号'))

    await waitFor(() => {
      expect(createMember).toHaveBeenCalledWith({
        url: '/workspaces/current/members',
        body: {
          email: 'new.user@example.com',
          name: 'New User',
          role: 'normal',
          password: 'newPassword123',
          password_confirm: 'newPassword123',
        },
      })
    })
    expect(mockRefetchMembers).toHaveBeenCalled()
    expect(mockToastSuccess).toHaveBeenCalledWith('账号已创建')
  })

  it('should reset a normal member password from the member row', async () => {
    renderConsole()
    openAccountsSection()

    fireEvent.click(screen.getAllByText('重置密码')[0]!)
    fireEvent.change(screen.getByLabelText('新密码'), { target: { value: 'resetPassword123' } })
    fireEvent.change(screen.getByLabelText('确认密码'), { target: { value: 'resetPassword123' } })
    fireEvent.click(screen.getByText('保存新密码'))

    await waitFor(() => {
      expect(resetMemberPassword).toHaveBeenCalledWith({
        url: '/workspaces/current/members/normal-id/password',
        body: {
          new_password: 'resetPassword123',
          password_confirm: 'resetPassword123',
        },
      })
    })
    expect(mockToastSuccess).toHaveBeenCalledWith('成员密码已重置')
  })

  it('should hide reset password for admin targets when current user is admin', () => {
    vi.mocked(useMembers).mockReturnValue({
      data: { accounts: [adminMember] },
      isLoading: false,
      refetch: mockRefetchMembers,
    } as unknown as ReturnType<typeof useMembers>)

    renderConsole({
      userProfile: { id: 'admin-current-id' },
      currentWorkspace: { role: 'admin' },
      isCurrentWorkspaceOwner: false,
    })
    openAccountsSection()

    expect(screen.queryByText('重置密码')).not.toBeInTheDocument()
  })

  it('should block submit when passwords do not match', async () => {
    renderConsole()
    openAccountsSection()

    fireEvent.click(screen.getByText('新增账号'))
    fireEvent.change(screen.getByLabelText('登录邮箱'), { target: { value: 'new.user@example.com' } })
    fireEvent.change(screen.getByLabelText('初始密码'), { target: { value: 'newPassword123' } })
    fireEvent.change(screen.getByLabelText('确认密码'), { target: { value: 'otherPassword123' } })
    fireEvent.click(screen.getByText('创建账号'))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('两次输入的密码不一致')
    })
    expect(createMember).not.toHaveBeenCalled()
  })
})
