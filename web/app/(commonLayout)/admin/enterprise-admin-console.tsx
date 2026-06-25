'use client'

import type { ReactNode } from 'react'
import type { AuditLogItem, PermissionTemplate, PermissionTemplatePayload } from '@/models/app'
import type { InvitationResult, IWorkspace, Member } from '@/models/common'
import type { DataSet } from '@/models/datasets'
import type { InstalledApp } from '@/models/explore'
import type { App } from '@/types/app'
import type { WorkspacePermission, WorkspacePermissionRisk, WorkspacePermissionScope, WorkspaceRole } from '@/utils/workspace-permissions'
import { toast } from '@langgenius/dify-ui/toast'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import InviteModal from '@/app/components/header/account-setting/members-page/invite-modal'
import InvitedModal from '@/app/components/header/account-setting/members-page/invited-modal'
import { useAppContext } from '@/context/app-context'
import { useProviderContext } from '@/context/provider-context'
import { DatasetPermission } from '@/models/datasets'
import Link from '@/next/link'
import { applyPermissionTemplate, createPermissionTemplate, deletePermissionTemplate, fetchAdminAuditLogs, fetchAppList, fetchAppPermissionMembers, fetchExploreAppPermissionMembers, fetchPermissionTemplates, updateAppPermissionMembers, updateExploreAppPermissionMembers, updatePermissionTemplate } from '@/service/apps'
import { deleteMemberOrCancelInvitation, updateMemberRole } from '@/service/common'
import { fetchDatasets, updateDatasetSetting } from '@/service/datasets'
import { fetchInstalledAppList } from '@/service/explore'
import { systemFeaturesQueryOptions } from '@/service/system-features'
import { useMembers, useWorkspaces } from '@/service/use-common'
import {
  enterpriseWorkspacePermissionPolicy,
  workspacePermissionKeys,
  workspacePermissionMetadata,
  workspacePermissionRoles,
} from '@/utils/workspace-permissions'

type AdminSection = 'accounts' | 'workspaces' | 'roles' | 'templates' | 'matrix' | 'explore' | 'apps' | 'datasets' | 'audit'

type PermissionTemplateFormState = PermissionTemplatePayload & { id?: string | null }

const emptyTemplateForm: PermissionTemplateFormState = {
  id: null,
  name: '',
  description: '',
  member_ids: [],
  app_ids: [],
  dataset_ids: [],
  explore_app_ids: [],
}

const adminSections: Array<{ key: AdminSection, label: string, icon: string, description: string }> = [
  { key: 'accounts', label: '账号管理', icon: 'i-ri-user-settings-line', description: '成员账号、状态和所属角色' },
  { key: 'workspaces', label: '工作区管理', icon: 'i-ri-building-4-line', description: '租户工作区和计划状态' },
  { key: 'roles', label: '成员角色', icon: 'i-ri-shield-user-line', description: '角色分布与职责边界' },
  { key: 'templates', label: '权限模板', icon: 'i-ri-git-branch-line', description: '批量授权成员和资源' },
  { key: 'matrix', label: '权限矩阵', icon: 'i-ri-table-2', description: 'B+ 企业权限策略' },
  { key: 'explore', label: '探索应用权限', icon: 'i-ri-compass-3-line', description: '探索模块应用访问权限' },
  { key: 'apps', label: '工作室应用权限', icon: 'i-ri-apps-2-line', description: '工作室应用访问权限' },
  { key: 'datasets', label: '知识库权限', icon: 'i-ri-database-2-line', description: '知识库访问和成员权限' },
  { key: 'audit', label: '审计日志', icon: 'i-ri-file-search-line', description: 'Plus 风格操作记录入口' },
]

const orderedRoles: WorkspaceRole[] = ['owner', 'admin', 'editor', 'dataset_operator', 'normal']
const editableRoles: WorkspaceRole[] = ['admin', 'editor', 'dataset_operator', 'normal']

const roleLabelMap: Record<WorkspaceRole, string> = {
  owner: '所有者',
  admin: '管理员',
  editor: '编辑者',
  dataset_operator: '知识库管理员',
  normal: '普通成员',
}

const roleDescriptionMap: Record<WorkspaceRole, string> = {
  owner: '拥有工作区、成员、合规和转移所有权等全部控制权。',
  admin: '负责日常管理、成员、应用 API Key、模型和工具配置。',
  editor: '可以创建、编辑、发布应用和维护知识库，不能管理工作区。',
  dataset_operator: '专注知识库创建、编辑和维护，不进入应用管理面。',
  normal: '以查看和使用为主，可访问应用、工具、插件和探索面。',
}

const statusLabelMap: Record<Member['status'], string> = {
  pending: '待加入',
  active: '正常',
  banned: '禁用',
  closed: '关闭',
}

const statusClassMap: Record<Member['status'], string> = {
  pending: 'border-amber-200 bg-amber-50 text-amber-700',
  active: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  banned: 'border-red-200 bg-red-50 text-red-700',
  closed: 'border-gray-200 bg-gray-50 text-gray-600',
}

const riskLabelMap: Record<WorkspacePermissionRisk, string> = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '关键',
}

const riskClassMap: Record<WorkspacePermissionRisk, string> = {
  low: 'bg-slate-100 text-slate-600',
  medium: 'bg-blue-50 text-blue-700',
  high: 'bg-amber-50 text-amber-700',
  critical: 'bg-red-50 text-red-700',
}

const scopeLabelMap: Record<WorkspacePermissionScope, string> = {
  workspace: '工作区',
  app: '应用',
  dataset: '知识库',
  provider: '模型与工具',
  plugin: '插件',
  navigation: '导航',
}

const permissionLabelMap: Record<WorkspacePermission, string> = {
  'workspace.view': '查看工作区',
  'workspace.update': '更新工作区',
  'workspace.member.view': '查看成员',
  'workspace.member.manage': '管理成员',
  'workspace.owner.transfer': '转移所有权',
  'workspace.billing.manage': '管理计费',
  'workspace.compliance.manage': '合规配置',
  'workspace.brand.manage': '品牌配置',
  'app.view': '查看应用',
  'app.create': '创建应用',
  'app.edit': '编辑应用',
  'app.delete': '删除应用',
  'app.publish': '发布应用',
  'app.access-control.manage': '应用访问控制',
  'app.api-key.manage': 'API Key 管理',
  'dataset.view': '查看知识库',
  'dataset.create': '创建知识库',
  'dataset.edit': '编辑知识库',
  'dataset.delete': '删除知识库',
  'dataset.member-permission.manage': '知识库成员权限',
  'model-provider.manage': '模型供应商管理',
  'tool-provider.manage': '工具供应商管理',
  'plugin.view': '查看插件',
  'plugin.manage': '管理插件',
  'explore.view': '查看探索',
  'tools.view': '查看工具',
}

const appModeLabelMap: Record<string, string> = {
  'completion': '文本生成',
  'workflow': '工作流',
  'chat': '聊天助手',
  'advanced-chat': '高级聊天',
  'agent-chat': 'Agent',
}

const datasetPermissionLabelMap: Record<string, string> = {
  only_me: '仅创建者',
  all_team_members: '全体成员',
  partial_members: '指定成员',
}

const formatDateTime = (value?: string | number | null) => {
  if (!value)
    return '暂无'

  const time = typeof value === 'number' ? value * 1000 : value
  const date = new Date(time)
  if (Number.isNaN(date.getTime()))
    return '暂无'

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

const getRoleCount = (members: Member[], role: WorkspaceRole) => members.filter(member => member.role === role).length

const hasRolePermission = (role: WorkspaceRole, permission: WorkspacePermission) => {
  return (workspacePermissionRoles[permission] as readonly WorkspaceRole[]).includes(role)
}

const SectionHeader = ({ title, description, action }: { title: string, description: string, action?: ReactNode }) => (
  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-divider-subtle px-6 py-5">
    <div>
      <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
      <p className="mt-1 text-sm text-text-tertiary">{description}</p>
    </div>
    {action}
  </div>
)

const Metric = ({ label, value, hint }: { label: string, value: string | number, hint: string }) => (
  <div className="border-r border-divider-subtle px-5 py-4 last:border-r-0">
    <div className="text-2xl font-semibold text-text-primary">{value}</div>
    <div className="mt-1 text-sm font-medium text-text-secondary">{label}</div>
    <div className="mt-1 text-xs text-text-tertiary">{hint}</div>
  </div>
)

const EmptyTable = ({ text }: { text: string }) => (
  <div className="flex h-40 items-center justify-center border-t border-divider-subtle text-sm text-text-tertiary">
    {text}
  </div>
)

export default function EnterpriseAdminConsole() {
  const [activeSection, setActiveSection] = useState<AdminSection>('accounts')
  const [keyword, setKeyword] = useState('')
  const [operatingMemberId, setOperatingMemberId] = useState<string | null>(null)
  const [inviteModalVisible, setInviteModalVisible] = useState(false)
  const [invitedModalVisible, setInvitedModalVisible] = useState(false)
  const [invitationResults, setInvitationResults] = useState<InvitationResult[]>([])
  const [selectedAppForAccess, setSelectedAppForAccess] = useState<App | null>(null)
  const [selectedExploreAppForAccess, setSelectedExploreAppForAccess] = useState<InstalledApp | null>(null)
  const [selectedDatasetForAccess, setSelectedDatasetForAccess] = useState<DataSet | null>(null)
  const [selectedAppMemberIds, setSelectedAppMemberIds] = useState<string[]>([])
  const [selectedExploreAppMemberIds, setSelectedExploreAppMemberIds] = useState<string[]>([])
  const [datasetMemberIds, setDatasetMemberIds] = useState<string[]>([])
  const [savingAppAccess, setSavingAppAccess] = useState(false)
  const [savingExploreAppAccess, setSavingExploreAppAccess] = useState(false)
  const [savingDatasetAccess, setSavingDatasetAccess] = useState(false)
  const [templateForm, setTemplateForm] = useState<PermissionTemplateFormState>(emptyTemplateForm)
  const [savingTemplate, setSavingTemplate] = useState(false)
  const [applyingTemplateId, setApplyingTemplateId] = useState<string | null>(null)
  const [deletingTemplateId, setDeletingTemplateId] = useState<string | null>(null)
  const { currentWorkspace, isCurrentWorkspaceManager, canAny } = useAppContext()
  const { datasetOperatorEnabled } = useProviderContext()
  const hasAnyPermission = canAny ?? (() => false)

  const canEnterAdmin = hasAnyPermission(['workspace.member.view', 'workspace.member.manage']) || isCurrentWorkspaceManager
  const canViewApps = hasAnyPermission(['app.view'])
  const canViewExplore = hasAnyPermission(['explore.view'])
  const canViewDatasets = hasAnyPermission(['dataset.view'])

  const { data: membersData, isLoading: isMembersLoading, refetch: refetchMembers } = useMembers()
  const { data: workspacesData, isLoading: isWorkspacesLoading, refetch: refetchWorkspaces } = useWorkspaces()
  const { data: systemFeatures } = useQuery(systemFeaturesQueryOptions())

  const appsQuery = useQuery({
    queryKey: ['enterprise-admin', 'apps'],
    queryFn: () => fetchAppList({ url: '/apps', params: { page: 1, limit: 100 } }),
    enabled: canEnterAdmin && canViewApps,
  })

  const exploreAppsQuery = useQuery({
    queryKey: ['enterprise-admin', 'explore-apps'],
    queryFn: () => fetchInstalledAppList(),
    enabled: canEnterAdmin && canViewExplore,
  })

  const datasetsQuery = useQuery({
    queryKey: ['enterprise-admin', 'datasets'],
    queryFn: () => fetchDatasets({ url: '/datasets', params: { page: 1, limit: 100 } }),
    enabled: canEnterAdmin && canViewDatasets,
  })

  const auditQuery = useQuery({
    queryKey: ['enterprise-admin', 'audit'],
    queryFn: fetchAdminAuditLogs,
    enabled: canEnterAdmin,
  })

  const templatesQuery = useQuery({
    queryKey: ['enterprise-admin', 'permission-templates'],
    queryFn: fetchPermissionTemplates,
    enabled: canEnterAdmin,
  })

  const members = membersData?.accounts ?? []
  const workspaces = workspacesData?.workspaces ?? []
  const apps = appsQuery.data?.data ?? []
  const exploreApps = exploreAppsQuery.data?.installed_apps ?? []
  const datasets = datasetsQuery.data?.data ?? []
  const auditLogs = auditQuery.data?.data ?? []
  const permissionTemplates = templatesQuery.data?.data ?? []

  const filteredMembers = useMemo(() => {
    const nextKeyword = keyword.trim().toLowerCase()
    if (!nextKeyword)
      return members

    return members.filter((member) => {
      return [member.name, member.email, roleLabelMap[member.role], statusLabelMap[member.status]]
        .filter(Boolean)
        .some(value => value?.toLowerCase().includes(nextKeyword))
    })
  }, [keyword, members])

  const roleStats = useMemo(() => orderedRoles.map(role => ({
    role,
    label: roleLabelMap[role],
    description: roleDescriptionMap[role],
    count: getRoleCount(members, role),
    permissionCount: workspacePermissionKeys.filter(permission => hasRolePermission(role, permission)).length,
  })), [members])

  const scopeStats = useMemo(() => {
    return Object.entries(scopeLabelMap).map(([scope, label]) => {
      const permissions = workspacePermissionKeys.filter(permission => workspacePermissionMetadata[permission].scope === scope)
      return { scope: scope as WorkspacePermissionScope, label, count: permissions.length }
    })
  }, [])

  const refetchActive = () => {
    if (activeSection === 'accounts' || activeSection === 'roles')
      void refetchMembers()
    if (activeSection === 'workspaces')
      void refetchWorkspaces()
    if (activeSection === 'apps')
      void appsQuery.refetch()
    if (activeSection === 'explore')
      void exploreAppsQuery.refetch()
    if (activeSection === 'datasets')
      void datasetsQuery.refetch()
    if (activeSection === 'templates')
      void templatesQuery.refetch()
    if (activeSection === 'audit')
      void auditQuery.refetch()
  }

  const canOperateMember = (member: Member) => {
    if (!currentWorkspace || member.role === 'owner')
      return false

    if (currentWorkspace.role === 'owner')
      return true

    return currentWorkspace.role === 'admin'
  }

  const roleOptions = editableRoles.filter(role => role !== 'dataset_operator' || datasetOperatorEnabled)

  const handleUpdateMemberRole = async (member: Member, nextRole: WorkspaceRole) => {
    if (member.role === nextRole)
      return

    setOperatingMemberId(member.id)
    try {
      await updateMemberRole({
        url: `/workspaces/current/members/${member.id}/update-role`,
        body: { role: nextRole },
      })
      await refetchMembers()
      toast.success('成员角色已更新')
    }
    finally {
      setOperatingMemberId(null)
    }
  }

  const handleRemoveMember = async (member: Member) => {
    setOperatingMemberId(member.id)
    try {
      await deleteMemberOrCancelInvitation({ url: `/workspaces/current/members/${member.id}` })
      await refetchMembers()
      toast.success('成员已移除')
    }
    finally {
      setOperatingMemberId(null)
    }
  }

  const openAppAccess = async (app: App) => {
    setSelectedAppForAccess(app)
    const result = await fetchAppPermissionMembers({ appID: app.id })
    setSelectedAppMemberIds(result.data ?? [])
  }

  const openExploreAppAccess = async (installedApp: InstalledApp) => {
    setSelectedExploreAppForAccess(installedApp)
    const result = await fetchExploreAppPermissionMembers({ appID: installedApp.app.id })
    setSelectedExploreAppMemberIds(result.data ?? [])
  }

  const openDatasetAccess = (dataset: DataSet) => {
    setSelectedDatasetForAccess(dataset)
    setDatasetMemberIds(dataset.partial_member_list ?? [])
  }

  const toggleAppMember = (memberId: string) => {
    setSelectedAppMemberIds((current) => {
      if (current.includes(memberId))
        return current.filter(id => id !== memberId)

      return [...current, memberId]
    })
  }

  const toggleExploreAppMember = (memberId: string) => {
    setSelectedExploreAppMemberIds((current) => {
      if (current.includes(memberId))
        return current.filter(id => id !== memberId)

      return [...current, memberId]
    })
  }

  const toggleDatasetMember = (memberId: string) => {
    setDatasetMemberIds((current) => {
      if (current.includes(memberId))
        return current.filter(id => id !== memberId)

      return [...current, memberId]
    })
  }

  const toggleTemplateValue = (field: 'member_ids' | 'app_ids' | 'dataset_ids' | 'explore_app_ids', id: string) => {
    setTemplateForm((current) => {
      const values = current[field]
      return {
        ...current,
        [field]: values.includes(id) ? values.filter(value => value !== id) : [...values, id],
      }
    })
  }

  const editTemplate = (template: PermissionTemplate) => {
    setTemplateForm({
      id: template.id,
      name: template.name,
      description: template.description ?? '',
      member_ids: template.member_ids,
      app_ids: template.app_ids,
      dataset_ids: template.dataset_ids,
      explore_app_ids: template.explore_app_ids ?? [],
    })
  }

  const resetTemplateForm = () => {
    setTemplateForm(emptyTemplateForm)
  }

  const handleSaveTemplate = async () => {
    const name = templateForm.name.trim()
    if (!name) {
      toast.error('请填写模板名称')
      return
    }

    setSavingTemplate(true)
    const body: PermissionTemplatePayload = {
      name,
      description: templateForm.description?.trim() || null,
      member_ids: templateForm.member_ids,
      app_ids: templateForm.app_ids,
      dataset_ids: templateForm.dataset_ids,
      explore_app_ids: templateForm.explore_app_ids,
    }
    try {
      if (templateForm.id)
        await updatePermissionTemplate({ templateID: templateForm.id, body })
      else
        await createPermissionTemplate(body)

      await templatesQuery.refetch()
      await auditQuery.refetch()
      resetTemplateForm()
      toast.success('权限模板已保存')
    }
    finally {
      setSavingTemplate(false)
    }
  }

  const handleApplyTemplate = async (template: PermissionTemplate) => {
    setApplyingTemplateId(template.id)
    try {
      const result = await applyPermissionTemplate(template.id)
      await Promise.all([exploreAppsQuery.refetch(), appsQuery.refetch(), datasetsQuery.refetch(), auditQuery.refetch()])
      toast.success(`模板已应用：${result.data.member_count} 个成员，${result.data.explore_app_count} 个探索应用，${result.data.app_count} 个工作室应用，${result.data.dataset_count} 个知识库`)
    }
    finally {
      setApplyingTemplateId(null)
    }
  }

  const handleDeleteTemplate = async (template: PermissionTemplate) => {
    setDeletingTemplateId(template.id)
    try {
      await deletePermissionTemplate(template.id)
      await templatesQuery.refetch()
      await auditQuery.refetch()
      if (templateForm.id === template.id)
        resetTemplateForm()
      toast.success('权限模板已删除')
    }
    finally {
      setDeletingTemplateId(null)
    }
  }

  const handleSaveAppAccess = async () => {
    if (!selectedAppForAccess)
      return

    setSavingAppAccess(true)
    try {
      await updateAppPermissionMembers({
        appID: selectedAppForAccess.id,
        body: {
          partial_member_list: selectedAppMemberIds.map(id => ({
            user_id: id,
            role: members.find(item => item.id === id)?.role ?? 'normal',
          })),
        },
      })
      await appsQuery.refetch()
      await auditQuery.refetch()
      setSelectedAppForAccess(null)
      toast.success('工作室应用授权已更新')
    }
    finally {
      setSavingAppAccess(false)
    }
  }

  const handleSaveExploreAppAccess = async () => {
    if (!selectedExploreAppForAccess)
      return

    setSavingExploreAppAccess(true)
    try {
      await updateExploreAppPermissionMembers({
        appID: selectedExploreAppForAccess.app.id,
        body: {
          partial_member_list: selectedExploreAppMemberIds.map(id => ({
            user_id: id,
            role: members.find(item => item.id === id)?.role ?? 'normal',
          })),
        },
      })
      await exploreAppsQuery.refetch()
      await auditQuery.refetch()
      setSelectedExploreAppForAccess(null)
      toast.success('探索应用授权已更新')
    }
    finally {
      setSavingExploreAppAccess(false)
    }
  }

  const handleSaveDatasetAccess = async () => {
    if (!selectedDatasetForAccess)
      return

    setSavingDatasetAccess(true)
    try {
      await updateDatasetSetting({
        datasetId: selectedDatasetForAccess.id,
        body: {
          permission: DatasetPermission.partialMembers,
          partial_member_list: datasetMemberIds.map((id) => {
            const member = members.find(item => item.id === id)
            return { user_id: id, role: member?.role ?? 'normal' }
          }),
        },
      })
      await datasetsQuery.refetch()
      setSelectedDatasetForAccess(null)
      toast.success('知识库授权已更新')
    }
    finally {
      setSavingDatasetAccess(false)
    }
  }

  if (!canEnterAdmin) {
    return (
      <div className="flex min-h-[calc(100vh-56px)] items-center justify-center bg-background-body px-6">
        <div className="w-full max-w-xl border border-divider-subtle bg-background-section p-8 text-center shadow-xs">
          <div className="mx-auto flex size-12 items-center justify-center rounded-lg bg-red-50 text-red-600">
            <span className="i-ri-lock-2-line size-6" aria-hidden />
          </div>
          <h1 className="mt-5 text-xl font-semibold text-text-primary">暂无企业管理权限</h1>
          <p className="mt-2 text-sm leading-6 text-text-tertiary">
            企业管理入口仅对工作区所有者和管理员开放。当前账号没有查看成员或管理工作区的权限。
          </p>
          <Link href="/apps" className="mt-6 inline-flex h-9 items-center rounded-md bg-components-button-primary-bg px-4 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover">
            返回应用列表
          </Link>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-[calc(100vh-56px)] bg-background-body text-text-primary">
      <div className="border-b border-divider-subtle bg-background-section">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-4 px-8 py-5">
          <div>
            <div className="text-xs font-semibold text-text-tertiary uppercase">MMB Enterprise Admin</div>
            <h1 className="mt-1 text-2xl font-semibold text-text-primary">企业管理后台</h1>
            <p className="mt-1 text-sm text-text-tertiary">
              参考企业级权限管理结构，聚合当前工作区的账号、角色、权限和资源治理入口。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="inline-flex h-9 items-center gap-2 rounded-md border border-divider-deep bg-background-default px-3 text-sm font-medium text-text-secondary hover:bg-background-default-hover"
              onClick={refetchActive}
            >
              <span className="i-ri-refresh-line size-4" aria-hidden />
              刷新当前页
            </button>
            <Link href="/apps" className="inline-flex h-9 items-center gap-2 rounded-md bg-components-button-primary-bg px-3 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover">
              <span className="i-ri-apps-line size-4" aria-hidden />
              返回 AI 中台
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-[1440px] grid-cols-[260px_1fr] gap-0 px-8 py-6 max-lg:grid-cols-1 max-lg:px-4">
        <aside className="border border-divider-subtle bg-background-section max-lg:mb-4">
          <div className="border-b border-divider-subtle px-4 py-4">
            <div className="text-sm font-semibold text-text-primary">{currentWorkspace?.name ?? '当前工作区'}</div>
            <div className="mt-1 text-xs text-text-tertiary">
              当前角色：
              {currentWorkspace?.role ? roleLabelMap[currentWorkspace.role] : '未知'}
            </div>
          </div>
          <nav className="p-2">
            {adminSections.map(section => (
              <button
                key={section.key}
                type="button"
                className={`mb-1 flex w-full items-start gap-3 rounded-md px-3 py-3 text-left transition-colors ${activeSection === section.key ? 'bg-blue-50 text-blue-700' : 'text-text-secondary hover:bg-background-default-hover'}`}
                onClick={() => setActiveSection(section.key)}
              >
                <span className={`${section.icon} mt-0.5 size-4 shrink-0`} aria-hidden />
                <span className="min-w-0">
                  <span className="block text-sm font-medium">{section.label}</span>
                  <span className="mt-0.5 block truncate text-xs opacity-75">{section.description}</span>
                </span>
              </button>
            ))}
          </nav>
        </aside>

        <section className="min-w-0 border-y border-r border-divider-subtle bg-background-section max-lg:border-l">
          <div className="grid grid-cols-4 border-b border-divider-subtle max-xl:grid-cols-2 max-sm:grid-cols-1">
            <Metric label="成员账号" value={members.length} hint="来自当前工作区成员接口" />
            <Metric label="工作区" value={workspaces.length} hint="当前账号可见租户" />
            <Metric label="应用" value={appsQuery.isLoading ? '...' : apps.length} hint="可见应用样本" />
            <Metric label="知识库" value={datasetsQuery.isLoading ? '...' : datasets.length} hint="可见知识库样本" />
          </div>

          {activeSection === 'accounts' && (
            <div>
              <SectionHeader
                title="账号管理"
                description="按企业级用户管理表格逻辑整理：账号、邮箱、角色、状态和活跃时间。"
                action={(
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="inline-flex h-9 items-center gap-2 rounded-md bg-components-button-primary-bg px-3 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover"
                      onClick={() => setInviteModalVisible(true)}
                    >
                      <span className="i-ri-user-add-line size-4" aria-hidden />
                      新增账号
                    </button>
                    <label className="relative block w-72 max-sm:w-full">
                      <span className="pointer-events-none absolute top-1/2 left-3 i-ri-search-line size-4 -translate-y-1/2 text-text-tertiary" aria-hidden />
                      <input
                        value={keyword}
                        onChange={event => setKeyword(event.target.value)}
                        placeholder="搜索账号、邮箱、角色或状态"
                        className="h-9 w-full rounded-md border border-divider-deep bg-background-default pr-3 pl-9 text-sm text-text-primary outline-none focus:border-blue-400"
                      />
                    </label>
                  </div>
                )}
              />
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="bg-background-default text-xs font-medium text-text-tertiary">
                    <tr>
                      <th className="px-6 py-3">账号</th>
                      <th className="px-4 py-3">角色</th>
                      <th className="px-4 py-3">状态</th>
                      <th className="px-4 py-3">最近活跃</th>
                      <th className="px-4 py-3">创建时间</th>
                      <th className="px-4 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-divider-subtle">
                    {filteredMembers.map(member => (
                      <tr key={member.id} className="hover:bg-background-default-hover">
                        <td className="px-6 py-4">
                          <div className="font-medium text-text-primary">{member.name || '未命名账号'}</div>
                          <div className="mt-1 text-xs text-text-tertiary">{member.email}</div>
                        </td>
                        <td className="px-4 py-4 text-text-secondary">{roleLabelMap[member.role]}</td>
                        <td className="px-4 py-4">
                          <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${statusClassMap[member.status]}`}>{statusLabelMap[member.status]}</span>
                        </td>
                        <td className="px-4 py-4 text-text-secondary">{formatDateTime(member.last_active_at || member.last_login_at)}</td>
                        <td className="px-4 py-4 text-text-tertiary">{formatDateTime(member.created_at)}</td>
                        <td className="px-4 py-4">
                          <div className="flex items-center justify-end gap-2">
                            {canOperateMember(member)
                              ? (
                                  <>
                                    <select
                                      aria-label="更新成员角色"
                                      className="h-8 rounded-md border border-divider-deep bg-background-default px-2 text-xs text-text-secondary outline-none hover:bg-background-default-hover focus:border-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
                                      value={member.role}
                                      disabled={operatingMemberId === member.id}
                                      onChange={event => void handleUpdateMemberRole(member, event.target.value as WorkspaceRole)}
                                    >
                                      {roleOptions.map(role => (
                                        <option key={role} value={role}>{roleLabelMap[role]}</option>
                                      ))}
                                    </select>
                                    <button
                                      type="button"
                                      className="inline-flex h-8 items-center rounded-md border border-red-200 bg-red-50 px-2 text-xs font-medium text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                                      disabled={operatingMemberId === member.id}
                                      onClick={() => void handleRemoveMember(member)}
                                    >
                                      移除
                                    </button>
                                  </>
                                )
                              : <span className="text-xs text-text-tertiary">不可编辑</span>}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!isMembersLoading && filteredMembers.length === 0 && <EmptyTable text="没有匹配的账号" />}
            </div>
          )}

          {activeSection === 'workspaces' && (
            <div>
              <SectionHeader title="工作区管理" description="对齐 Plus 租户管理入口，展示当前账号可访问的工作区、计划和状态。" />
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="bg-background-default text-xs font-medium text-text-tertiary">
                    <tr>
                      <th className="px-6 py-3">工作区</th>
                      <th className="px-4 py-3">计划</th>
                      <th className="px-4 py-3">状态</th>
                      <th className="px-4 py-3">当前</th>
                      <th className="px-4 py-3">创建时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-divider-subtle">
                    {workspaces.map((workspace: IWorkspace) => (
                      <tr key={workspace.id} className="hover:bg-background-default-hover">
                        <td className="px-6 py-4 font-medium text-text-primary">{workspace.name}</td>
                        <td className="px-4 py-4 text-text-secondary">{workspace.plan || '默认'}</td>
                        <td className="px-4 py-4 text-text-secondary">{workspace.status || '正常'}</td>
                        <td className="px-4 py-4 text-text-secondary">{workspace.current ? '是' : '否'}</td>
                        <td className="px-4 py-4 text-text-tertiary">{formatDateTime(workspace.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!isWorkspacesLoading && workspaces.length === 0 && <EmptyTable text="暂无可管理工作区" />}
            </div>
          )}

          {activeSection === 'roles' && (
            <div>
              <SectionHeader title="成员角色" description="角色职责和人数分布直接来自当前成员数据，职责边界沿用 B+ 权限策略。" />
              <div className="divide-y divide-divider-subtle">
                {roleStats.map(role => (
                  <div key={role.role} className="grid grid-cols-[180px_1fr_120px_140px] items-center gap-4 px-6 py-4 max-lg:grid-cols-1">
                    <div>
                      <div className="font-semibold text-text-primary">{role.label}</div>
                      <div className="mt-1 text-xs text-text-tertiary">{role.role}</div>
                    </div>
                    <div className="text-sm text-text-secondary">{role.description}</div>
                    <div className="text-sm text-text-secondary">
                      成员：
                      <span className="font-semibold text-text-primary">{role.count}</span>
                    </div>
                    <div className="text-sm text-text-secondary">
                      权限：
                      <span className="font-semibold text-text-primary">{role.permissionCount}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeSection === 'templates' && (
            <div>
              <SectionHeader
                title="权限模板"
                description="按部门或岗位维护一组成员、探索应用、工作室应用和知识库，应用模板时会追加授权到现有资源，不覆盖手工授权。"
                action={templateForm.id
                  ? (
                      <button
                        type="button"
                        className="inline-flex h-9 items-center gap-2 rounded-md border border-divider-deep bg-background-default px-3 text-sm font-medium text-text-secondary hover:bg-background-default-hover"
                        onClick={resetTemplateForm}
                      >
                        <span className="i-ri-add-line size-4" aria-hidden />
                        新建模板
                      </button>
                    )
                  : null}
              />
              <div className="grid grid-cols-[360px_1fr] gap-0 max-xl:grid-cols-1">
                <div className="border-r border-divider-subtle p-5 max-xl:border-r-0 max-xl:border-b">
                  <div className="text-sm font-semibold text-text-primary">{templateForm.id ? '编辑模板' : '新建模板'}</div>
                  <div className="mt-4 space-y-4">
                    <label className="block">
                      <span className="text-xs font-medium text-text-tertiary">模板名称</span>
                      <input
                        value={templateForm.name}
                        onChange={event => setTemplateForm(current => ({ ...current, name: event.target.value }))}
                        placeholder="例如：A 部门通用权限"
                        className="mt-1 h-9 w-full rounded-md border border-divider-deep bg-background-default px-3 text-sm text-text-primary outline-none focus:border-blue-400"
                      />
                    </label>
                    <label className="block">
                      <span className="text-xs font-medium text-text-tertiary">说明</span>
                      <textarea
                        value={templateForm.description ?? ''}
                        onChange={event => setTemplateForm(current => ({ ...current, description: event.target.value }))}
                        placeholder="用于记录模板适用部门、岗位或审批口径"
                        className="mt-1 min-h-20 w-full resize-none rounded-md border border-divider-deep bg-background-default px-3 py-2 text-sm text-text-primary outline-none focus:border-blue-400"
                      />
                    </label>
                    <TemplatePicker
                      title="成员"
                      emptyText="暂无成员"
                      items={members.map(member => ({ id: member.id, title: member.name || member.email, subtitle: `${member.email} · ${roleLabelMap[member.role]}` }))}
                      selectedIds={templateForm.member_ids}
                      onToggle={id => toggleTemplateValue('member_ids', id)}
                    />
                    <TemplatePicker
                      title="探索应用"
                      emptyText={canViewExplore ? '暂无探索应用' : '当前角色没有查看探索权限'}
                      items={exploreApps.map(installedApp => ({ id: installedApp.app.id, title: installedApp.app.name, subtitle: appModeLabelMap[installedApp.app.mode] || installedApp.app.mode }))}
                      selectedIds={templateForm.explore_app_ids}
                      onToggle={id => toggleTemplateValue('explore_app_ids', id)}
                    />
                    <TemplatePicker
                      title="工作室应用"
                      emptyText={canViewApps ? '暂无工作室应用' : '当前角色没有查看工作室应用权限'}
                      items={apps.map(app => ({ id: app.id, title: app.name, subtitle: appModeLabelMap[app.mode] || app.mode }))}
                      selectedIds={templateForm.app_ids}
                      onToggle={id => toggleTemplateValue('app_ids', id)}
                    />
                    <TemplatePicker
                      title="知识库"
                      emptyText={canViewDatasets ? '暂无知识库' : '当前角色没有查看知识库权限'}
                      items={datasets.map(dataset => ({ id: dataset.id, title: dataset.name, subtitle: datasetPermissionLabelMap[dataset.permission] || dataset.permission }))}
                      selectedIds={templateForm.dataset_ids}
                      onToggle={id => toggleTemplateValue('dataset_ids', id)}
                    />
                    <button
                      type="button"
                      className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-md bg-components-button-primary-bg px-3 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={savingTemplate}
                      onClick={() => void handleSaveTemplate()}
                    >
                      <span className="i-ri-save-line size-4" aria-hidden />
                      {savingTemplate ? '保存中...' : '保存模板'}
                    </button>
                  </div>
                </div>
                <div className="min-w-0">
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[780px] text-left text-sm">
                      <thead className="bg-background-default text-xs font-medium text-text-tertiary">
                        <tr>
                          <th className="px-6 py-3">模板</th>
                          <th className="px-4 py-3">成员</th>
                          <th className="px-4 py-3">探索应用</th>
                          <th className="px-4 py-3">工作室应用</th>
                          <th className="px-4 py-3">知识库</th>
                          <th className="px-4 py-3">更新时间</th>
                          <th className="px-4 py-3 text-right">操作</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-divider-subtle">
                        {permissionTemplates.map(template => (
                          <tr key={template.id} className="hover:bg-background-default-hover">
                            <td className="px-6 py-4">
                              <div className="font-medium text-text-primary">{template.name}</div>
                              <div className="mt-1 line-clamp-1 text-xs text-text-tertiary">{template.description || '暂无说明'}</div>
                            </td>
                            <td className="px-4 py-4 text-text-secondary">{template.member_count}</td>
                            <td className="px-4 py-4 text-text-secondary">{template.explore_app_count ?? 0}</td>
                            <td className="px-4 py-4 text-text-secondary">{template.app_count}</td>
                            <td className="px-4 py-4 text-text-secondary">{template.dataset_count}</td>
                            <td className="px-4 py-4 text-text-tertiary">{formatDateTime(template.updated_at || template.created_at)}</td>
                            <td className="px-4 py-4">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  type="button"
                                  className="inline-flex h-8 items-center rounded-md border border-divider-deep bg-background-default px-2 text-xs font-medium text-text-secondary hover:bg-background-default-hover"
                                  onClick={() => editTemplate(template)}
                                >
                                  编辑
                                </button>
                                <button
                                  type="button"
                                  className="inline-flex h-8 items-center rounded-md bg-components-button-primary-bg px-2 text-xs font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
                                  disabled={applyingTemplateId === template.id}
                                  onClick={() => void handleApplyTemplate(template)}
                                >
                                  {applyingTemplateId === template.id ? '应用中...' : '应用'}
                                </button>
                                <button
                                  type="button"
                                  className="inline-flex h-8 items-center rounded-md border border-red-200 bg-red-50 px-2 text-xs font-medium text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                                  disabled={deletingTemplateId === template.id}
                                  onClick={() => void handleDeleteTemplate(template)}
                                >
                                  删除
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!templatesQuery.isLoading && permissionTemplates.length === 0 && <EmptyTable text="暂无权限模板" />}
                </div>
              </div>
            </div>
          )}

          {activeSection === 'matrix' && (
            <div>
              <SectionHeader title="权限矩阵" description={`策略版本：${enterpriseWorkspacePermissionPolicy.version}。按 Plus 角色-菜单-资源权限思路，用当前 B+ 策略生成矩阵。`} />
              <div className="flex flex-wrap gap-2 px-6 py-4">
                {scopeStats.map(scope => (
                  <span key={scope.scope} className="rounded-md border border-divider-subtle bg-background-default px-2.5 py-1 text-xs text-text-secondary">
                    {scope.label}
                    ：
                    {scope.count}
                    {' '}
                    项
                  </span>
                ))}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[980px] text-left text-sm">
                  <thead className="bg-background-default text-xs font-medium text-text-tertiary">
                    <tr>
                      <th className="px-6 py-3">权限</th>
                      <th className="px-4 py-3">模块</th>
                      <th className="px-4 py-3">风险</th>
                      {orderedRoles.map(role => <th key={role} className="px-4 py-3 text-center">{roleLabelMap[role]}</th>)}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-divider-subtle">
                    {workspacePermissionKeys.map((permission) => {
                      const metadata = workspacePermissionMetadata[permission]
                      return (
                        <tr key={permission} className="hover:bg-background-default-hover">
                          <td className="px-6 py-3">
                            <div className="font-medium text-text-primary">{permissionLabelMap[permission]}</div>
                            <div className="mt-0.5 text-xs text-text-tertiary">{permission}</div>
                          </td>
                          <td className="px-4 py-3 text-text-secondary">{scopeLabelMap[metadata.scope]}</td>
                          <td className="px-4 py-3">
                            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${riskClassMap[metadata.risk]}`}>{riskLabelMap[metadata.risk]}</span>
                          </td>
                          {orderedRoles.map(role => (
                            <td key={role} className="px-4 py-3 text-center">
                              {hasRolePermission(role, permission)
                                ? <span className="mx-auto i-ri-check-line block size-4 text-emerald-600" aria-label="允许" />
                                : <span className="mx-auto i-ri-subtract-line block size-4 text-text-quaternary" aria-label="不允许" />}
                            </td>
                          ))}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeSection === 'explore' && (
            <div>
              <SectionHeader title="探索应用权限" description="展示探索模块里已安装的应用，并集中管理这些应用在探索入口的可见和运行成员。" />
              <PermissionStrip permissions={workspacePermissionKeys.filter(permission => workspacePermissionMetadata[permission].scope === 'navigation' && permission === 'explore.view')} />
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="bg-background-default text-xs font-medium text-text-tertiary">
                    <tr>
                      <th className="px-6 py-3">探索应用</th>
                      <th className="px-4 py-3">类型</th>
                      <th className="px-4 py-3">固定</th>
                      <th className="px-4 py-3">可卸载</th>
                      <th className="px-4 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-divider-subtle">
                    {exploreApps.map((installedApp: InstalledApp) => (
                      <tr key={installedApp.id} className="hover:bg-background-default-hover">
                        <td className="px-6 py-4">
                          <div className="font-medium text-text-primary">{installedApp.app.name}</div>
                          <div className="mt-1 line-clamp-1 text-xs text-text-tertiary">{installedApp.app.id}</div>
                        </td>
                        <td className="px-4 py-4 text-text-secondary">{appModeLabelMap[installedApp.app.mode] || installedApp.app.mode}</td>
                        <td className="px-4 py-4 text-text-secondary">{installedApp.is_pinned ? '是' : '否'}</td>
                        <td className="px-4 py-4 text-text-secondary">{installedApp.uninstallable ? '是' : '否'}</td>
                        <td className="px-4 py-4 text-right">
                          <button
                            type="button"
                            className="inline-flex h-8 items-center rounded-md border border-divider-deep bg-background-default px-2 text-xs font-medium text-text-secondary hover:bg-background-default-hover"
                            onClick={() => void openExploreAppAccess(installedApp)}
                          >
                            授权成员
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!exploreAppsQuery.isLoading && exploreApps.length === 0 && <EmptyTable text={canViewExplore ? '暂无可见探索应用' : '当前角色没有查看探索权限'} />}
            </div>
          )}

          {activeSection === 'apps' && (
            <div>
              <SectionHeader title="工作室应用权限" description="展示工作室里的应用，并集中管理这些应用的可见成员；探索应用和编排编辑权限属于独立权限层级。" />
              <PermissionStrip permissions={workspacePermissionKeys.filter(permission => workspacePermissionMetadata[permission].scope === 'app')} />
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-left text-sm">
                  <thead className="bg-background-default text-xs font-medium text-text-tertiary">
                    <tr>
                      <th className="px-6 py-3">工作室应用</th>
                      <th className="px-4 py-3">类型</th>
                      <th className="px-4 py-3">站点</th>
                      <th className="px-4 py-3">API</th>
                      <th className="px-4 py-3">访问模式</th>
                      <th className="px-4 py-3">更新时间</th>
                      <th className="px-4 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-divider-subtle">
                    {apps.map((app: App) => (
                      <tr key={app.id} className="hover:bg-background-default-hover">
                        <td className="px-6 py-4">
                          <div className="font-medium text-text-primary">{app.name}</div>
                          <div className="mt-1 line-clamp-1 text-xs text-text-tertiary">{app.description || '暂无描述'}</div>
                        </td>
                        <td className="px-4 py-4 text-text-secondary">{appModeLabelMap[app.mode] || app.mode}</td>
                        <td className="px-4 py-4 text-text-secondary">{app.enable_site ? '已启用' : '未启用'}</td>
                        <td className="px-4 py-4 text-text-secondary">{app.enable_api ? '已启用' : '未启用'}</td>
                        <td className="px-4 py-4 text-text-secondary">{app.access_mode || '默认'}</td>
                        <td className="px-4 py-4 text-text-tertiary">{formatDateTime(app.updated_at)}</td>
                        <td className="px-4 py-4 text-right">
                          <button
                            type="button"
                            className="inline-flex h-8 items-center rounded-md border border-divider-deep bg-background-default px-2 text-xs font-medium text-text-secondary hover:bg-background-default-hover"
                            onClick={() => void openAppAccess(app)}
                          >
                            授权成员
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!appsQuery.isLoading && apps.length === 0 && <EmptyTable text={canViewApps ? '暂无可见工作室应用' : '当前角色没有查看工作室应用权限'} />}
            </div>
          )}

          {activeSection === 'datasets' && (
            <div>
              <SectionHeader title="知识库权限" description="对齐 Plus 的资源权限思路，集中查看知识库列表、成员可见性和知识库权限策略。" />
              <PermissionStrip permissions={workspacePermissionKeys.filter(permission => workspacePermissionMetadata[permission].scope === 'dataset')} />
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-left text-sm">
                  <thead className="bg-background-default text-xs font-medium text-text-tertiary">
                    <tr>
                      <th className="px-6 py-3">知识库</th>
                      <th className="px-4 py-3">可见范围</th>
                      <th className="px-4 py-3">文档</th>
                      <th className="px-4 py-3">关联应用</th>
                      <th className="px-4 py-3">索引状态</th>
                      <th className="px-4 py-3">更新时间</th>
                      <th className="px-4 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-divider-subtle">
                    {datasets.map((dataset: DataSet) => (
                      <tr key={dataset.id} className="hover:bg-background-default-hover">
                        <td className="px-6 py-4">
                          <div className="font-medium text-text-primary">{dataset.name}</div>
                          <div className="mt-1 line-clamp-1 text-xs text-text-tertiary">{dataset.description || '暂无描述'}</div>
                        </td>
                        <td className="px-4 py-4 text-text-secondary">{datasetPermissionLabelMap[dataset.permission] || dataset.permission}</td>
                        <td className="px-4 py-4 text-text-secondary">{dataset.document_count ?? 0}</td>
                        <td className="px-4 py-4 text-text-secondary">{dataset.app_count ?? 0}</td>
                        <td className="px-4 py-4 text-text-secondary">{dataset.indexing_status || '未知'}</td>
                        <td className="px-4 py-4 text-text-tertiary">{formatDateTime(dataset.updated_at)}</td>
                        <td className="px-4 py-4 text-right">
                          <button
                            type="button"
                            className="inline-flex h-8 items-center rounded-md border border-divider-deep bg-background-default px-2 text-xs font-medium text-text-secondary hover:bg-background-default-hover"
                            onClick={() => openDatasetAccess(dataset)}
                          >
                            授权成员
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!datasetsQuery.isLoading && datasets.length === 0 && <EmptyTable text={canViewDatasets ? '暂无可见知识库' : '当前角色没有查看知识库权限'} />}
            </div>
          )}

          {activeSection === 'audit' && (
            <div>
              <SectionHeader title="审计日志" description="读取当前工作区最近的管理操作记录，优先覆盖成员授权等高风险动作。" />
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-left text-sm">
                  <thead className="bg-background-default text-xs font-medium text-text-tertiary">
                    <tr>
                      <th className="px-6 py-3">动作</th>
                      <th className="px-4 py-3">操作人</th>
                      <th className="px-4 py-3">时间</th>
                      <th className="px-4 py-3">IP</th>
                      <th className="px-4 py-3">内容</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-divider-subtle">
                    {auditLogs.map((log: AuditLogItem) => {
                      const operator = members.find(member => member.id === log.account_id)
                      return (
                        <tr key={log.id} className="hover:bg-background-default-hover">
                          <td className="px-6 py-4 font-medium text-text-primary">{log.action}</td>
                          <td className="px-4 py-4 text-text-secondary">{operator?.email || log.account_id}</td>
                          <td className="px-4 py-4 text-text-tertiary">{formatDateTime(log.created_at)}</td>
                          <td className="px-4 py-4 text-text-tertiary">{log.created_ip}</td>
                          <td className="px-4 py-4 text-xs text-text-tertiary">{log.content ? JSON.stringify(log.content) : '暂无'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {!auditQuery.isLoading && auditLogs.length === 0 && <EmptyTable text="暂无审计记录" />}
            </div>
          )}
        </section>
      </div>

      {inviteModalVisible && (
        <InviteModal
          isEmailSetup={systemFeatures?.is_email_setup ?? false}
          onCancel={() => setInviteModalVisible(false)}
          onSend={(results) => {
            setInviteModalVisible(false)
            setInvitationResults(results)
            setInvitedModalVisible(true)
            void refetchMembers()
          }}
        />
      )}
      {invitedModalVisible && (
        <InvitedModal
          invitationResults={invitationResults}
          onCancel={() => setInvitedModalVisible(false)}
        />
      )}
      {selectedExploreAppForAccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-xl rounded-lg bg-background-section shadow-xl">
            <div className="border-b border-divider-subtle px-5 py-4">
              <h3 className="text-base font-semibold text-text-primary">探索应用授权成员</h3>
              <p className="mt-1 text-sm text-text-tertiary">
                将「
                {selectedExploreAppForAccess.app.name}
                」设置为指定成员可在探索模块查看和运行。保存后会写入当前工作区的探索应用授权表。
              </p>
            </div>
            <div className="max-h-[420px] overflow-y-auto px-5 py-3">
              {members.map(member => (
                <label key={member.id} className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 hover:bg-background-default-hover">
                  <input
                    type="checkbox"
                    className="size-4 rounded border-divider-deep text-components-button-primary-bg focus:ring-components-button-primary-bg"
                    checked={selectedExploreAppMemberIds.includes(member.id)}
                    onChange={() => toggleExploreAppMember(member.id)}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-text-primary">{member.name || member.email}</span>
                    <span className="mt-0.5 block truncate text-xs text-text-tertiary">
                      {member.email}
                      {' '}
                      ·
                      {' '}
                      {roleLabelMap[member.role]}
                    </span>
                  </span>
                  <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusClassMap[member.status]}`}>{statusLabelMap[member.status]}</span>
                </label>
              ))}
              {members.length === 0 && (
                <div className="py-12 text-center text-sm text-text-tertiary">暂无可授权成员</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-divider-subtle px-5 py-4">
              <button
                type="button"
                className="inline-flex h-9 items-center rounded-md border border-divider-deep bg-background-default px-4 text-sm font-medium text-text-secondary hover:bg-background-default-hover"
                onClick={() => setSelectedExploreAppForAccess(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="inline-flex h-9 items-center rounded-md bg-components-button-primary-bg px-4 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
                disabled={savingExploreAppAccess}
                onClick={() => void handleSaveExploreAppAccess()}
              >
                {savingExploreAppAccess ? '保存中...' : '保存授权'}
              </button>
            </div>
          </div>
        </div>
      )}
      {selectedAppForAccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-xl rounded-lg bg-background-section shadow-xl">
            <div className="border-b border-divider-subtle px-5 py-4">
              <h3 className="text-base font-semibold text-text-primary">工作室应用授权成员</h3>
              <p className="mt-1 text-sm text-text-tertiary">
                将「
                {selectedAppForAccess.name}
                」设置为指定成员可访问。保存后会写入当前工作区的工作室应用授权表。
              </p>
            </div>
            <div className="max-h-[420px] overflow-y-auto px-5 py-3">
              {members.map(member => (
                <label key={member.id} className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 hover:bg-background-default-hover">
                  <input
                    type="checkbox"
                    className="size-4 rounded border-divider-deep text-components-button-primary-bg focus:ring-components-button-primary-bg"
                    checked={selectedAppMemberIds.includes(member.id)}
                    onChange={() => toggleAppMember(member.id)}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-text-primary">{member.name || member.email}</span>
                    <span className="mt-0.5 block truncate text-xs text-text-tertiary">
                      {member.email}
                      {' '}
                      ·
                      {' '}
                      {roleLabelMap[member.role]}
                    </span>
                  </span>
                  <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusClassMap[member.status]}`}>{statusLabelMap[member.status]}</span>
                </label>
              ))}
              {members.length === 0 && (
                <div className="py-12 text-center text-sm text-text-tertiary">暂无可授权成员</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-divider-subtle px-5 py-4">
              <button
                type="button"
                className="inline-flex h-9 items-center rounded-md border border-divider-deep bg-background-default px-4 text-sm font-medium text-text-secondary hover:bg-background-default-hover"
                onClick={() => setSelectedAppForAccess(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="inline-flex h-9 items-center rounded-md bg-components-button-primary-bg px-4 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
                disabled={savingAppAccess}
                onClick={() => void handleSaveAppAccess()}
              >
                {savingAppAccess ? '保存中...' : '保存授权'}
              </button>
            </div>
          </div>
        </div>
      )}
      {selectedDatasetForAccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-xl rounded-lg bg-background-section shadow-xl">
            <div className="border-b border-divider-subtle px-5 py-4">
              <h3 className="text-base font-semibold text-text-primary">知识库授权成员</h3>
              <p className="mt-1 text-sm text-text-tertiary">
                将「
                {selectedDatasetForAccess.name}
                」设置为指定成员可访问。保存后会写入当前 MMBAI 知识库权限。
              </p>
            </div>
            <div className="max-h-[420px] overflow-y-auto px-5 py-3">
              {members.map(member => (
                <label key={member.id} className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 hover:bg-background-default-hover">
                  <input
                    type="checkbox"
                    className="size-4 rounded border-divider-deep text-components-button-primary-bg focus:ring-components-button-primary-bg"
                    checked={datasetMemberIds.includes(member.id)}
                    onChange={() => toggleDatasetMember(member.id)}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-text-primary">{member.name || member.email}</span>
                    <span className="mt-0.5 block truncate text-xs text-text-tertiary">
                      {member.email}
                      {' '}
                      ·
                      {' '}
                      {roleLabelMap[member.role]}
                    </span>
                  </span>
                  <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusClassMap[member.status]}`}>{statusLabelMap[member.status]}</span>
                </label>
              ))}
              {members.length === 0 && (
                <div className="py-12 text-center text-sm text-text-tertiary">暂无可授权成员</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-divider-subtle px-5 py-4">
              <button
                type="button"
                className="inline-flex h-9 items-center rounded-md border border-divider-deep bg-background-default px-4 text-sm font-medium text-text-secondary hover:bg-background-default-hover"
                onClick={() => setSelectedDatasetForAccess(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="inline-flex h-9 items-center rounded-md bg-components-button-primary-bg px-4 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
                disabled={savingDatasetAccess}
                onClick={() => void handleSaveDatasetAccess()}
              >
                {savingDatasetAccess ? '保存中...' : '保存授权'}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

function TemplatePicker({
  title,
  emptyText,
  items,
  selectedIds,
  onToggle,
}: {
  title: string
  emptyText: string
  items: Array<{ id: string, title: string, subtitle: string }>
  selectedIds: string[]
  onToggle: (id: string) => void
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs font-medium text-text-tertiary">
        <span>{title}</span>
        <span>{selectedIds.length}</span>
      </div>
      <div className="max-h-44 overflow-y-auto rounded-md border border-divider-subtle bg-background-default p-1">
        {items.map(item => (
          <label key={item.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-2 hover:bg-background-default-hover">
            <input
              type="checkbox"
              className="size-4 rounded border-divider-deep text-components-button-primary-bg focus:ring-components-button-primary-bg"
              checked={selectedIds.includes(item.id)}
              onChange={() => onToggle(item.id)}
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-text-primary">{item.title}</span>
              <span className="mt-0.5 block truncate text-xs text-text-tertiary">{item.subtitle}</span>
            </span>
          </label>
        ))}
        {items.length === 0 && <div className="px-2 py-8 text-center text-sm text-text-tertiary">{emptyText}</div>}
      </div>
    </div>
  )
}

function PermissionStrip({ permissions }: { permissions: WorkspacePermission[] }) {
  return (
    <div className="flex flex-wrap gap-2 border-b border-divider-subtle px-6 py-4">
      {permissions.map((permission) => {
        const metadata = workspacePermissionMetadata[permission]
        return (
          <span key={permission} className="inline-flex items-center gap-2 rounded-md border border-divider-subtle bg-background-default px-2.5 py-1 text-xs text-text-secondary">
            <span className={`size-1.5 rounded-full ${metadata.risk === 'critical' || metadata.risk === 'high' ? 'bg-amber-500' : 'bg-emerald-500'}`} aria-hidden />
            {permissionLabelMap[permission]}
          </span>
        )
      })}
    </div>
  )
}
