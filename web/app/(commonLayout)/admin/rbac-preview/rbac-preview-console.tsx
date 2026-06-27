'use client'

import type { ReactNode } from 'react'
import type { AuditLogItem, EffectivePermissionResource, PermissionGroup, PermissionGroupPayload, PermissionTemplate, PermissionTemplatePayload, RbacPreviewTab } from '@/models/app'
import type { Member } from '@/models/common'
import type { DataSet } from '@/models/datasets'
import type { InstalledApp } from '@/models/explore'
import type { App } from '@/types/app'
import { toast } from '@langgenius/dify-ui/toast'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useAppContext } from '@/context/app-context'
import { DatasetPermission } from '@/models/datasets'
import Link from '@/next/link'
import { applyPermissionTemplate, createPermissionGroup, createPermissionTemplate, deletePermissionGroup, deletePermissionTemplate, fetchAdminAuditLogs, fetchAppList, fetchAppPermissionMembers, fetchEffectivePermissions, fetchExploreAppPermissionMembers, fetchPermissionGroups, fetchPermissionTemplates, fetchWorkspaceUiPolicy, updateAdminUiPolicy, updateAppPermissionMembers, updateExploreAppPermissionMembers, updatePermissionGroup, updatePermissionTemplate } from '@/service/apps'
import { fetchDatasets, updateDatasetSetting } from '@/service/datasets'
import { fetchInstalledAppList } from '@/service/explore'
import { useMembers } from '@/service/use-common'

const roleLabelMap: Record<Member['role'], string> = { owner: '所有者', admin: '管理员', editor: '编辑者', dataset_operator: '知识库管理员', normal: '普通成员' }
const statusLabelMap: Record<Member['status'], string> = { pending: '待加入', active: '正常', banned: '禁用', closed: '关闭' }
const appModeLabelMap: Record<string, string> = { 'completion': '文本生成', 'workflow': '工作流', 'chat': '聊天助手', 'advanced-chat': '高级聊天', 'agent-chat': 'Agent' }
const datasetPermissionLabelMap: Record<string, string> = { only_me: '仅创建者', all_team_members: '全体成员', partial_members: '指定成员' }
const sourceLabelMap: Record<string, string> = { workspace_role: '工作区角色', direct: '直接授权', group_template: '用户组模板', direct_template: '模板直接成员' }
const sourceClassMap: Record<string, string> = { workspace_role: 'bg-blue-50 text-blue-700', direct: 'bg-emerald-50 text-emerald-700', group_template: 'bg-purple-50 text-purple-700', direct_template: 'bg-amber-50 text-amber-700' }

const tabs: Array<{ key: RbacPreviewTab, label: string, icon: string, desc: string }> = [
  { key: 'members', label: '成员目录', icon: 'i-ri-user-search-line', desc: '搜索成员、筛选状态、批量入组' },
  { key: 'groups', label: '用户组/部门', icon: 'i-ri-group-line', desc: '部门、岗位、项目组成员维护' },
  { key: 'templates', label: '权限模板', icon: 'i-ri-shield-keyhole-line', desc: '用户组到资源的授权策略' },
  { key: 'effective', label: '有效权限', icon: 'i-ri-focus-3-line', desc: '解释账号最终能看见什么' },
  { key: 'resources', label: '资源直授权', icon: 'i-ri-apps-2-line', desc: '低频排查入口' },
  { key: 'audit', label: '审计日志', icon: 'i-ri-file-search-line', desc: 'RBAC 相关操作记录' },
  { key: 'general', label: '通用', icon: 'i-ri-settings-3-line', desc: '全局界面策略' },
]

type MemberSortKey = 'account' | 'role' | 'status' | 'group' | 'created_at'
type SortDirection = 'asc' | 'desc'
type MemberSortState = { key: MemberSortKey, direction: SortDirection }

const emptyGroup = { id: null, name: '', description: '', member_ids: [] } satisfies PermissionGroupPayload & { id: string | null }
const emptyTemplate = { id: null, name: '', description: '', member_ids: [], group_ids: [], app_ids: [], dataset_ids: [], explore_app_ids: [] } satisfies PermissionTemplatePayload & { id: string | null }
const toggle = (list: string[], id: string) => list.includes(id) ? list.filter(item => item !== id) : [...list, id]
const collator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })
const match = (keyword: string, values: Array<string | null | undefined>) => !keyword.trim() || values.filter(Boolean).some(value => value!.toLowerCase().includes(keyword.trim().toLowerCase()))
const fmt = (value?: string | number | null) => {
  if (!value)
    return '暂无'
  const date = new Date(typeof value === 'number' ? value * 1000 : value)
  return Number.isNaN(date.getTime()) ? '暂无' : new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date)
}

export default function RbacPreviewConsole() {
  const [activeTab, setActiveTab] = useState<RbacPreviewTab>('members')
  const [keyword, setKeyword] = useState('')
  const [selectedMemberIds, setSelectedMemberIds] = useState<string[]>([])
  const [roleFilter, setRoleFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [groupFilter, setGroupFilter] = useState('all')
  const [batchGroupId, setBatchGroupId] = useState('')
  const [memberSort, setMemberSort] = useState<MemberSortState>({ key: 'created_at', direction: 'desc' })
  const [groupForm, setGroupForm] = useState<PermissionGroupPayload & { id: string | null }>(emptyGroup)
  const [templateForm, setTemplateForm] = useState<PermissionTemplatePayload & { id: string | null }>(emptyTemplate)
  const [effectiveMemberId, setEffectiveMemberId] = useState('')
  const [selectedResource, setSelectedResource] = useState<{ kind: 'app' | 'explore' | 'dataset', id: string } | null>(null)
  const [resourceMemberIds, setResourceMemberIds] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [updatingUiPolicy, setUpdatingUiPolicy] = useState(false)
  const [editorPanel, setEditorPanel] = useState<'group' | 'template' | 'resource' | 'effective' | 'audit' | null>(null)
  const [selectedAuditLog, setSelectedAuditLog] = useState<AuditLogItem | null>(null)
  const { currentWorkspace, isCurrentWorkspaceManager, canAny } = useAppContext()
  const hasAnyPermission = canAny ?? (() => false)
  const canEnterAdmin = hasAnyPermission(['workspace.member.view', 'workspace.member.manage']) || isCurrentWorkspaceManager
  const { data: membersData, isLoading: membersLoading, refetch: refetchMembers } = useMembers()
  const members = useMemo(() => membersData?.accounts ?? [], [membersData?.accounts])
  const appsQuery = useQuery({ queryKey: ['rbac-preview', 'apps'], queryFn: () => fetchAppList({ url: '/apps', params: { page: 1, limit: 100 } }), enabled: canEnterAdmin })
  const exploreQuery = useQuery({ queryKey: ['rbac-preview', 'explore-apps'], queryFn: () => fetchInstalledAppList(), enabled: canEnterAdmin })
  const datasetsQuery = useQuery({ queryKey: ['rbac-preview', 'datasets'], queryFn: () => fetchDatasets({ url: '/datasets', params: { page: 1, limit: 100 } }), enabled: canEnterAdmin })
  const groupsQuery = useQuery({ queryKey: ['rbac-preview', 'groups'], queryFn: fetchPermissionGroups, enabled: canEnterAdmin })
  const templatesQuery = useQuery({ queryKey: ['rbac-preview', 'templates'], queryFn: fetchPermissionTemplates, enabled: canEnterAdmin })
  const auditQuery = useQuery({ queryKey: ['rbac-preview', 'audit'], queryFn: fetchAdminAuditLogs, enabled: canEnterAdmin })
  const uiPolicyQuery = useQuery({ queryKey: ['rbac-preview', 'ui-policy'], queryFn: fetchWorkspaceUiPolicy, enabled: canEnterAdmin })
  const activeEffectiveMemberId = effectiveMemberId || members[0]?.id || ''
  const effectiveQuery = useQuery({ queryKey: ['rbac-preview', 'effective', activeEffectiveMemberId], queryFn: () => fetchEffectivePermissions(activeEffectiveMemberId), enabled: canEnterAdmin && (activeTab === 'effective' || editorPanel === 'effective') && !!activeEffectiveMemberId })
  const apps = useMemo(() => appsQuery.data?.data ?? [], [appsQuery.data?.data])
  const exploreApps = useMemo(() => exploreQuery.data?.installed_apps ?? [], [exploreQuery.data?.installed_apps])
  const datasets = useMemo(() => datasetsQuery.data?.data ?? [], [datasetsQuery.data?.data])
  const groups = useMemo(() => groupsQuery.data?.data ?? [], [groupsQuery.data?.data])
  const templates = useMemo(() => templatesQuery.data?.data ?? [], [templatesQuery.data?.data])
  const auditLogs = useMemo(() => auditQuery.data?.data ?? [], [auditQuery.data?.data])
  const currentTab = tabs.find(tab => tab.key === activeTab) ?? tabs[0]!
  const showUnauthorizedResourceCards = uiPolicyQuery.data?.show_unauthorized_resource_cards ?? false
  const groupsByMember = useMemo(() => {
    const map = new Map<string, PermissionGroup[]>()
    groups.forEach(group => group.member_ids.forEach(memberId => map.set(memberId, [...(map.get(memberId) ?? []), group])))
    return map
  }, [groups])
  const templateCountByGroup = useMemo(() => {
    const map = new Map<string, number>()
    templates.forEach(template => template.group_ids.forEach(groupId => map.set(groupId, (map.get(groupId) ?? 0) + 1)))
    return map
  }, [templates])
  const filteredMembers = useMemo(() => members.filter((member) => {
    const memberGroups = groupsByMember.get(member.id) ?? []
    return (roleFilter === 'all' || member.role === roleFilter)
      && (statusFilter === 'all' || member.status === statusFilter)
      && (groupFilter === 'all' || (groupFilter === 'none' ? memberGroups.length === 0 : memberGroups.some(group => group.id === groupFilter)))
      && match(keyword, [member.name, member.email, roleLabelMap[member.role], statusLabelMap[member.status], ...memberGroups.map(group => group.name)])
  }), [groupFilter, groupsByMember, keyword, members, roleFilter, statusFilter])
  const sortedMembers = useMemo(() => {
    const direction = memberSort.direction === 'asc' ? 1 : -1
    const accountName = (member: Member) => `${member.name || ''} ${member.email}`
    const groupName = (member: Member) => (groupsByMember.get(member.id) ?? []).map(group => group.name).join('、') || '未入组'
    const createdAt = (member: Member) => {
      if (!member.created_at)
        return 0
      const date = new Date(member.created_at)
      return Number.isNaN(date.getTime()) ? 0 : date.getTime()
    }

    return [...filteredMembers].sort((a, b) => {
      let result = 0
      if (memberSort.key === 'created_at')
        result = createdAt(a) - createdAt(b)
      else if (memberSort.key === 'role')
        result = collator.compare(roleLabelMap[a.role], roleLabelMap[b.role])
      else if (memberSort.key === 'status')
        result = collator.compare(statusLabelMap[a.status], statusLabelMap[b.status])
      else if (memberSort.key === 'group')
        result = collator.compare(groupName(a), groupName(b))
      else result = collator.compare(accountName(a), accountName(b))

      return result === 0 ? collator.compare(accountName(a), accountName(b)) : result * direction
    })
  }, [filteredMembers, groupsByMember, memberSort.direction, memberSort.key])
  const filteredGroups = useMemo(() => groups.filter(group => match(keyword, [group.name, group.description])), [groups, keyword])
  const filteredTemplates = useMemo(() => templates.filter(template => match(keyword, [template.name, template.description])), [templates, keyword])
  const filteredAuditLogs = useMemo(() => auditLogs.filter(log => log.action.includes('permission_') || log.action.includes('app_permissions') || log.action.includes('dataset')), [auditLogs])
  const resources = useMemo(() => {
    const appResources = apps.map(app => ({ id: app.id, kind: 'app' as const, name: app.name, subtitle: appModeLabelMap[app.mode] || app.mode }))
    const exploreResources = exploreApps.map(item => ({ id: item.app.id, kind: 'explore' as const, name: item.app.name, subtitle: appModeLabelMap[item.app.mode] || item.app.mode }))
    const datasetResources = datasets.map(dataset => ({ id: dataset.id, kind: 'dataset' as const, name: dataset.name, subtitle: datasetPermissionLabelMap[dataset.permission] || dataset.permission }))
    return [...exploreResources, ...appResources, ...datasetResources].filter(resource => match(keyword, [resource.name, resource.subtitle, resource.kind]))
  }, [apps, datasets, exploreApps, keyword])
  const templateEffectiveMembers = useMemo(() => {
    const ids = new Set(templateForm.member_ids)
    templateForm.group_ids.forEach(groupId => groups.find(group => group.id === groupId)?.member_ids.forEach(memberId => ids.add(memberId)))
    return ids.size
  }, [groups, templateForm.group_ids, templateForm.member_ids])
  const refreshAll = async () => {
    await Promise.all([refetchMembers(), appsQuery.refetch(), exploreQuery.refetch(), datasetsQuery.refetch(), groupsQuery.refetch(), templatesQuery.refetch(), auditQuery.refetch()])
    toast.success('数据已刷新')
  }
  const updateMemberSort = (key: MemberSortKey) => {
    setMemberSort(current => current.key === key
      ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
      : { key, direction: key === 'created_at' ? 'desc' : 'asc' })
  }
  const handleToggleUnauthorizedCards = async () => {
    if (updatingUiPolicy)
      return

    setUpdatingUiPolicy(true)
    try {
      await updateAdminUiPolicy({ show_unauthorized_resource_cards: !showUnauthorizedResourceCards })
      await uiPolicyQuery.refetch()
      toast.success('界面权限策略已更新')
    }
    catch (error) {
      toast.error(error instanceof Error ? error.message : '界面权限策略更新失败')
    }
    finally {
      setUpdatingUiPolicy(false)
    }
  }
  const saveGroup = async () => {
    if (!groupForm.name.trim()) {
      toast.error('请填写用户组名称')
      return
    }
    setSaving(true)
    try {
      const body = { name: groupForm.name.trim(), description: groupForm.description?.trim() || null, member_ids: groupForm.member_ids }
      if (groupForm.id)
        await updatePermissionGroup({ groupID: groupForm.id, body })
      else await createPermissionGroup(body)
      await Promise.all([groupsQuery.refetch(), templatesQuery.refetch(), effectiveQuery.refetch(), auditQuery.refetch()])
      setGroupForm(emptyGroup)
      setEditorPanel(null)
      toast.success('用户组已保存')
    }
    finally { setSaving(false) }
  }
  const copyGroup = async (group: PermissionGroup) => {
    setSaving(true)
    try {
      await createPermissionGroup({ name: `${group.name} 副本`, description: group.description, member_ids: group.member_ids })
      await groupsQuery.refetch()
      toast.success('用户组已复制')
    }
    finally { setSaving(false) }
  }
  const removeGroup = async (group: PermissionGroup) => {
    setSaving(true)
    try {
      await deletePermissionGroup(group.id)
      await Promise.all([groupsQuery.refetch(), templatesQuery.refetch(), effectiveQuery.refetch(), auditQuery.refetch()])
      if (groupForm.id === group.id) {
        setGroupForm(emptyGroup)
        setEditorPanel(null)
      }
      toast.success('用户组已删除')
    }
    finally { setSaving(false) }
  }
  const batchUpdateGroup = async (mode: 'add' | 'remove') => {
    const group = groups.find(item => item.id === batchGroupId)
    if (!group || selectedMemberIds.length === 0) {
      toast.error('请选择用户组和成员')
      return
    }
    const memberIds = mode === 'add' ? Array.from(new Set([...group.member_ids, ...selectedMemberIds])) : group.member_ids.filter(id => !selectedMemberIds.includes(id))
    setSaving(true)
    try {
      await updatePermissionGroup({ groupID: group.id, body: { name: group.name, description: group.description, member_ids: memberIds } })
      setSelectedMemberIds([])
      await Promise.all([groupsQuery.refetch(), templatesQuery.refetch(), effectiveQuery.refetch()])
      toast.success(mode === 'add' ? '成员已加入用户组' : '成员已移出用户组')
    }
    finally { setSaving(false) }
  }
  const editTemplate = (template: PermissionTemplate) => {
    setTemplateForm({ id: template.id, name: template.name, description: template.description ?? '', member_ids: template.member_ids ?? [], group_ids: template.group_ids ?? [], app_ids: template.app_ids, dataset_ids: template.dataset_ids, explore_app_ids: template.explore_app_ids ?? [] })
    setActiveTab('templates')
    setEditorPanel('template')
  }
  const saveTemplate = async () => {
    if (!templateForm.name.trim()) {
      toast.error('请填写模板名称')
      return
    }
    setSaving(true)
    try {
      const body: PermissionTemplatePayload = { name: templateForm.name.trim(), description: templateForm.description?.trim() || null, member_ids: templateForm.member_ids, group_ids: templateForm.group_ids, app_ids: templateForm.app_ids, dataset_ids: templateForm.dataset_ids, explore_app_ids: templateForm.explore_app_ids }
      if (templateForm.id)
        await updatePermissionTemplate({ templateID: templateForm.id, body })
      else await createPermissionTemplate(body)
      await Promise.all([templatesQuery.refetch(), appsQuery.refetch(), exploreQuery.refetch(), datasetsQuery.refetch(), effectiveQuery.refetch(), auditQuery.refetch()])
      setTemplateForm(emptyTemplate)
      setEditorPanel(null)
      toast.success('权限模板已保存')
    }
    finally { setSaving(false) }
  }
  const copyTemplate = async (template: PermissionTemplate) => {
    setSaving(true)
    try {
      await createPermissionTemplate({ name: `${template.name} 副本`, description: template.description, member_ids: template.member_ids ?? [], group_ids: template.group_ids ?? [], app_ids: template.app_ids, dataset_ids: template.dataset_ids, explore_app_ids: template.explore_app_ids ?? [] })
      await templatesQuery.refetch()
      toast.success('模板已复制')
    }
    finally { setSaving(false) }
  }
  const removeTemplate = async (template: PermissionTemplate) => {
    setSaving(true)
    try {
      await deletePermissionTemplate(template.id)
      await Promise.all([templatesQuery.refetch(), appsQuery.refetch(), exploreQuery.refetch(), datasetsQuery.refetch(), effectiveQuery.refetch(), auditQuery.refetch()])
      if (templateForm.id === template.id) {
        setTemplateForm(emptyTemplate)
        setEditorPanel(null)
      }
      toast.success('模板已删除')
    }
    finally { setSaving(false) }
  }
  const syncTemplate = async (template: PermissionTemplate) => {
    setSaving(true)
    try {
      const result = await applyPermissionTemplate(template.id)
      await Promise.all([appsQuery.refetch(), exploreQuery.refetch(), datasetsQuery.refetch(), effectiveQuery.refetch(), auditQuery.refetch()])
      toast.success(`已同步：${result.data.member_count} 个成员，${result.data.explore_app_count} 个探索应用，${result.data.app_count} 个工作室应用，${result.data.dataset_count} 个知识库`)
    }
    finally { setSaving(false) }
  }
  const openResource = async (resource: { kind: 'app' | 'explore' | 'dataset', id: string }) => {
    setSelectedResource(resource)
    if (resource.kind === 'app') {
      const result = await fetchAppPermissionMembers({ appID: resource.id })
      setResourceMemberIds(result.data ?? [])
    }
    else if (resource.kind === 'explore') {
      const result = await fetchExploreAppPermissionMembers({ appID: resource.id })
      setResourceMemberIds(result.data ?? [])
    }
    else {
      setResourceMemberIds(datasets.find(dataset => dataset.id === resource.id)?.partial_member_list ?? [])
    }
  }
  const saveResourceMembers = async () => {
    if (!selectedResource)
      return
    setSaving(true)
    try {
      const partial_member_list = resourceMemberIds.map(id => ({ user_id: id, role: members.find(member => member.id === id)?.role ?? 'normal' }))
      if (selectedResource.kind === 'app') {
        await updateAppPermissionMembers({ appID: selectedResource.id, body: { partial_member_list } })
        await appsQuery.refetch()
      }
      else if (selectedResource.kind === 'explore') {
        await updateExploreAppPermissionMembers({ appID: selectedResource.id, body: { partial_member_list } })
        await exploreQuery.refetch()
      }
      else {
        await updateDatasetSetting({ datasetId: selectedResource.id, body: { permission: DatasetPermission.partialMembers, partial_member_list } })
        await datasetsQuery.refetch()
      }
      await Promise.all([effectiveQuery.refetch(), auditQuery.refetch()])
      setEditorPanel(null)
      toast.success('资源直授权已保存')
    }
    finally { setSaving(false) }
  }

  const selectedResourceMeta = selectedResource
    ? resources.find(resource => resource.kind === selectedResource.kind && resource.id === selectedResource.id)
    : null

  const sectionAction = activeTab === 'groups'
    ? (
        <button
          type="button"
          className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-components-button-primary-bg px-3 text-xs font-medium text-components-button-primary-text shadow-xs hover:bg-components-button-primary-bg-hover"
          onClick={() => {
            setGroupForm(emptyGroup)
            setEditorPanel('group')
          }}
        >
          <span className="i-ri-add-line size-4" aria-hidden />
          新建用户组
        </button>
      )
    : activeTab === 'templates'
      ? (
          <button
            type="button"
            className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-components-button-primary-bg px-3 text-xs font-medium text-components-button-primary-text shadow-xs hover:bg-components-button-primary-bg-hover"
            onClick={() => {
              setTemplateForm(emptyTemplate)
              setEditorPanel('template')
            }}
          >
            <span className="i-ri-add-line size-4" aria-hidden />
            新建模板
          </button>
        )
      : null

  if (!canEnterAdmin)
    return <div className="flex h-full items-center justify-center bg-background-body text-sm text-text-tertiary">当前账号没有进入企业权限后台的权限。</div>

  return (
    <div className="min-h-screen bg-background-body text-text-primary">
      <div className="border-b border-divider-subtle bg-background-section">
        <div className="mx-auto flex max-w-[1520px] items-center justify-between gap-4 px-6 py-4 max-lg:flex-col max-lg:items-start">
          <div className="min-w-0">
            <div className="text-xs font-semibold text-text-tertiary uppercase">MMB Enterprise RBAC</div>
            <h1 className="mt-1 text-2xl font-semibold tracking-normal text-text-primary">企业权限控制台</h1>
            <p className="mt-1 text-sm text-text-tertiary">
              当前工作区：
              {currentWorkspace?.name || '暂无'}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button type="button" onClick={() => void refreshAll()} className="inline-flex h-9 items-center gap-2 rounded-lg border border-divider-subtle bg-background-section px-3 text-sm font-medium text-text-secondary shadow-xs hover:bg-background-default-hover">
              <span className="i-ri-refresh-line size-4" aria-hidden />
              刷新
            </button>
            <Link href="/apps" className="inline-flex h-9 items-center gap-2 rounded-lg bg-components-button-primary-bg px-3 text-sm font-medium text-components-button-primary-text shadow-xs hover:bg-components-button-primary-bg-hover">
              <span className="i-ri-apps-2-line size-4" aria-hidden />
              返回 AI 中台
            </Link>
          </div>
        </div>
        <div className="mx-auto grid max-w-[1520px] grid-cols-5 border-t border-divider-subtle px-6 max-lg:grid-cols-2 max-sm:grid-cols-1">
          <Metric label="成员" value={members.length} hint="当前工作区账号" />
          <Metric label="用户组" value={groups.length} hint="部门/岗位/项目组" />
          <Metric label="模板" value={templates.length} hint="批量授权策略" />
          <Metric label="应用" value={apps.length + exploreApps.length} hint="探索 + 工作室" />
          <Metric label="知识库" value={datasets.length} hint="可管理知识库" />
        </div>
      </div>
      <div className="mx-auto grid max-w-[1520px] grid-cols-[236px_minmax(0,1fr)] gap-4 px-6 py-5 max-xl:grid-cols-1 max-lg:px-4">
        <aside className="rounded-xl border border-divider-subtle bg-background-section p-3 shadow-xs max-xl:order-1">
          <div className="relative mb-3">
            <span className="absolute top-1/2 left-3 i-ri-search-line size-4 -translate-y-1/2 text-text-quaternary" aria-hidden />
            <input value={keyword} onChange={event => setKeyword(event.target.value)} placeholder="搜索成员、用户组、模板或资源" className="h-9 w-full rounded-lg border border-divider-subtle bg-background-default pr-3 pl-9 text-sm text-text-primary transition-colors outline-none placeholder:text-text-quaternary focus:border-blue-400 focus:bg-background-section" />
          </div>
          <nav className="space-y-0.5">
            {tabs.map(tab => (
              <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${activeTab === tab.key ? 'bg-blue-50 text-blue-700' : 'text-text-secondary hover:bg-background-default-hover'}`}>
                <span className={`flex size-7 shrink-0 items-center justify-center rounded-md ${activeTab === tab.key ? 'bg-white/70' : 'bg-background-default text-text-tertiary'}`}>
                  <span className={`${tab.icon} size-4`} aria-hidden />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">{tab.label}</span>
                  {activeTab === tab.key && <span className="mt-0.5 block truncate text-xs text-blue-700/70">{tab.desc}</span>}
                </span>
              </button>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 overflow-hidden rounded-xl border border-divider-subtle bg-background-section shadow-xs max-xl:order-2">
          <SectionTitle title={currentTab.label} description={currentTab.desc} action={sectionAction} />
          {activeTab === 'members' && (
            <MembersPanel
              members={sortedMembers}
              groupsByMember={groupsByMember}
              selectedMemberIds={selectedMemberIds}
              roleFilter={roleFilter}
              statusFilter={statusFilter}
              groupFilter={groupFilter}
              batchGroupId={batchGroupId}
              sort={memberSort}
              groups={groups}
              isLoading={membersLoading}
              saving={saving}
              onRoleFilterChange={setRoleFilter}
              onStatusFilterChange={setStatusFilter}
              onGroupFilterChange={setGroupFilter}
              onBatchGroupChange={setBatchGroupId}
              onSortChange={updateMemberSort}
              onToggleMember={id => setSelectedMemberIds(current => toggle(current, id))}
              onToggleAll={() => setSelectedMemberIds((current) => {
                const visibleIds = sortedMembers.map(member => member.id)
                const visibleIdSet = new Set(visibleIds)
                const allVisibleSelected = visibleIds.length > 0 && visibleIds.every(id => current.includes(id))
                return allVisibleSelected ? current.filter(id => !visibleIdSet.has(id)) : Array.from(new Set([...current, ...visibleIds]))
              })}
              onBatchUpdate={batchUpdateGroup}
              onOpenEffective={(id) => {
                setEffectiveMemberId(id)
                setEditorPanel('effective')
              }}
            />
          )}
          {activeTab === 'groups' && (
            <GroupsPanel
              groups={filteredGroups}
              templateCountByGroup={templateCountByGroup}
              saving={saving}
              onEdit={(group) => {
                setGroupForm({ id: group.id, name: group.name, description: group.description ?? '', member_ids: group.member_ids })
                setEditorPanel('group')
              }}
              onCopy={copyGroup}
              onRemove={removeGroup}
            />
          )}
          {activeTab === 'templates' && <TemplatesPanel templates={filteredTemplates} saving={saving} onEdit={editTemplate} onCopy={copyTemplate} onRemove={removeTemplate} onApply={syncTemplate} />}
          {activeTab === 'effective' && <EffectivePanel members={members} selectedMemberId={activeEffectiveMemberId} onSelectMember={setEffectiveMemberId} isLoading={effectiveQuery.isLoading} data={effectiveQuery.data?.data} />}
          {activeTab === 'resources' && (
            <ResourcesPanel
              resources={resources}
              selectedResource={selectedResource}
              onOpenResource={(resource) => {
                void openResource(resource).then(() => setEditorPanel('resource'))
              }}
            />
          )}
          {activeTab === 'audit' && (
            <AuditPanel
              logs={filteredAuditLogs}
              onOpenLog={(log) => {
                setSelectedAuditLog(log)
                setEditorPanel('audit')
              }}
            />
          )}
          {activeTab === 'general' && <GeneralSettingsPanel showUnauthorizedResourceCards={showUnauthorizedResourceCards} loading={uiPolicyQuery.isLoading || updatingUiPolicy} onToggle={() => void handleToggleUnauthorizedCards()} />}
        </main>
      </div>
      {editorPanel === 'group' && (
        <EditorDrawer title={groupForm.id ? '编辑用户组' : '新建用户组'} description="账号归属、部门和项目组在这里维护。" onClose={() => setEditorPanel(null)}>
          <GroupEditor form={groupForm} members={members} saving={saving} onChange={setGroupForm} onSave={saveGroup} onReset={() => setGroupForm(emptyGroup)} />
        </EditorDrawer>
      )}
      {editorPanel === 'template' && (
        <EditorDrawer title={templateForm.id ? '编辑权限模板' : '新建权限模板'} description="模板绑定用户组和资源，保存后可同步授权。" onClose={() => setEditorPanel(null)}>
          <TemplateEditor form={templateForm} groups={groups} apps={apps} exploreApps={exploreApps} datasets={datasets} effectiveMemberCount={templateEffectiveMembers} saving={saving} onChange={setTemplateForm} onSave={saveTemplate} onReset={() => setTemplateForm(emptyTemplate)} />
        </EditorDrawer>
      )}
      {editorPanel === 'resource' && selectedResource && (
        <EditorDrawer title="资源直授权" description={selectedResourceMeta ? `${selectedResourceMeta.name} · ${selectedResourceMeta.subtitle}` : '维护指定资源的可访问成员。'} onClose={() => setEditorPanel(null)}>
          <ResourceEditor selectedResource={selectedResource} members={members} memberIds={resourceMemberIds} saving={saving} onToggleMember={id => setResourceMemberIds(current => toggle(current, id))} onChangeMembers={setResourceMemberIds} onSave={saveResourceMembers} />
        </EditorDrawer>
      )}
      {editorPanel === 'effective' && (
        <EditorDrawer title="有效权限" description="只读查看该成员最终可见的资源和来源。" onClose={() => setEditorPanel(null)}>
          <EffectivePermissionDetail isLoading={effectiveQuery.isLoading} data={effectiveQuery.data?.data} />
        </EditorDrawer>
      )}
      {editorPanel === 'audit' && selectedAuditLog && (
        <EditorDrawer title="审计详情" description={fmt(selectedAuditLog.created_at)} onClose={() => setEditorPanel(null)}>
          <AuditLogDetail log={selectedAuditLog} />
        </EditorDrawer>
      )}
    </div>
  )
}

function EditorDrawer({ title, description, onClose, children }: { title: string, description: string, onClose: () => void, children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" className="absolute inset-0 cursor-default" aria-label="关闭编辑抽屉" onClick={onClose} />
      <div className="relative flex h-full w-full max-w-[560px] flex-col bg-background-section shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-divider-subtle px-6 py-5">
          <div className="min-w-0">
            <div className="text-base font-semibold text-text-primary">{title}</div>
            <div className="mt-1 text-sm text-text-tertiary">{description}</div>
          </div>
          <button type="button" className="flex size-8 shrink-0 items-center justify-center rounded-lg text-text-tertiary hover:bg-background-default-hover hover:text-text-secondary" aria-label="关闭" onClick={onClose}>
            <span className="i-ri-close-line size-4" aria-hidden />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {children}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value, hint }: { label: string, value: string | number, hint: string }) {
  return (
    <div className="border-r border-divider-subtle px-4 py-3 last:border-r-0 max-sm:border-r-0 max-sm:border-b">
      <div className="text-xl leading-6 font-semibold text-text-primary">{value}</div>
      <div className="mt-1 text-xs font-medium text-text-secondary">{label}</div>
      <div className="mt-0.5 truncate text-xs text-text-tertiary">{hint}</div>
    </div>
  )
}
function SectionTitle({ title, description, action }: { title: string, description: string, action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-divider-subtle px-5 py-4">
      <div className="min-w-0">
        <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
        <p className="mt-1 text-sm text-text-tertiary">{description}</p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
function EmptyState({ text }: { text: string }) {
  return <div className="flex h-40 items-center justify-center text-sm text-text-tertiary">{text}</div>
}

function MembersPanel({ members, groupsByMember, selectedMemberIds, roleFilter, statusFilter, groupFilter, batchGroupId, sort, groups, isLoading, saving, onRoleFilterChange, onStatusFilterChange, onGroupFilterChange, onBatchGroupChange, onSortChange, onToggleMember, onToggleAll, onBatchUpdate, onOpenEffective }: { members: Member[], groupsByMember: Map<string, PermissionGroup[]>, selectedMemberIds: string[], roleFilter: string, statusFilter: string, groupFilter: string, batchGroupId: string, sort: MemberSortState, groups: PermissionGroup[], isLoading: boolean, saving: boolean, onRoleFilterChange: (v: string) => void, onStatusFilterChange: (v: string) => void, onGroupFilterChange: (v: string) => void, onBatchGroupChange: (v: string) => void, onSortChange: (key: MemberSortKey) => void, onToggleMember: (id: string) => void, onToggleAll: () => void, onBatchUpdate: (mode: 'add' | 'remove') => void, onOpenEffective: (id: string) => void }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 border-b border-divider-subtle bg-background-default/40 px-5 py-3">
        <select value={roleFilter} onChange={e => onRoleFilterChange(e.target.value)} className="h-8 rounded-lg border border-divider-subtle bg-background-section px-2 text-xs text-text-secondary outline-none hover:bg-background-default-hover focus:border-blue-400">
          <option value="all">全部角色</option>
          {Object.entries(roleLabelMap).map(([role, label]) => <option key={role} value={role}>{label}</option>)}
        </select>
        <select value={statusFilter} onChange={e => onStatusFilterChange(e.target.value)} className="h-8 rounded-lg border border-divider-subtle bg-background-section px-2 text-xs text-text-secondary outline-none hover:bg-background-default-hover focus:border-blue-400">
          <option value="all">全部状态</option>
          {Object.entries(statusLabelMap).map(([status, label]) => <option key={status} value={status}>{label}</option>)}
        </select>
        <select value={groupFilter} onChange={e => onGroupFilterChange(e.target.value)} className="h-8 rounded-lg border border-divider-subtle bg-background-section px-2 text-xs text-text-secondary outline-none hover:bg-background-default-hover focus:border-blue-400">
          <option value="all">全部用户组</option>
          <option value="none">未入组</option>
          {groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}
        </select>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <span className="text-xs text-text-tertiary">
            已选
            {selectedMemberIds.length}
            {' '}
            人
          </span>
          <select value={batchGroupId} onChange={e => onBatchGroupChange(e.target.value)} className="h-8 rounded-lg border border-divider-subtle bg-background-section px-2 text-xs text-text-secondary outline-none hover:bg-background-default-hover focus:border-blue-400">
            <option value="">选择用户组</option>
            {groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}
          </select>
          <button disabled={saving} onClick={() => onBatchUpdate('add')} className="h-8 rounded-lg bg-components-button-primary-bg px-3 text-xs font-medium text-components-button-primary-text shadow-xs disabled:opacity-60">加入组</button>
          <button disabled={saving} onClick={() => onBatchUpdate('remove')} className="h-8 rounded-lg border border-divider-subtle bg-background-section px-3 text-xs font-medium text-text-secondary disabled:opacity-60">移出组</button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1120px] table-fixed text-left text-sm">
          <thead className="bg-background-default/70 text-xs text-text-tertiary">
            <tr>
              <th className="w-12 px-5 py-3"><input type="checkbox" checked={members.length > 0 && members.every(member => selectedMemberIds.includes(member.id))} onChange={onToggleAll} /></th>
              <SortableHeader label="账号" sortKey="account" activeSort={sort} onSort={onSortChange} className="w-[300px]" />
              <SortableHeader label="角色" sortKey="role" activeSort={sort} onSort={onSortChange} className="w-[112px]" />
              <SortableHeader label="状态" sortKey="status" activeSort={sort} onSort={onSortChange} className="w-[88px]" />
              <SortableHeader label="用户组" sortKey="group" activeSort={sort} onSort={onSortChange} className="w-[280px]" />
              <SortableHeader label="加入日期" sortKey="created_at" activeSort={sort} onSort={onSortChange} className="w-[132px]" />
              <th className="w-20 px-4 py-3 text-right whitespace-nowrap">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-divider-subtle">
            {members.map(member => (
              <tr key={member.id} className="hover:bg-background-default-hover">
                <td className="px-5 py-3"><input type="checkbox" checked={selectedMemberIds.includes(member.id)} onChange={() => onToggleMember(member.id)} /></td>
                <td className="px-4 py-3">
                  <div className="font-medium">{member.name || '未命名账号'}</div>
                  <div className="mt-1 text-xs text-text-tertiary">{member.email}</div>
                </td>
                <td className="px-4 py-3 text-text-secondary">{roleLabelMap[member.role]}</td>
                <td className="px-4 py-3 whitespace-nowrap text-text-secondary">{statusLabelMap[member.status]}</td>
                <td className="px-4 py-3 text-text-secondary">{(groupsByMember.get(member.id) ?? []).map(group => group.name).join('、') || '未入组'}</td>
                <td className="px-4 py-3 whitespace-nowrap text-text-secondary">{fmt(member.created_at)}</td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <button className="inline-flex h-7 items-center rounded-md px-2 text-xs font-medium text-text-tertiary hover:bg-blue-50 hover:text-blue-700" onClick={() => onOpenEffective(member.id)}>权限</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!isLoading && members.length === 0 && <EmptyState text="没有匹配的成员" />}
    </div>
  )
}

function SortableHeader({ label, sortKey, activeSort, onSort, className = '' }: { label: string, sortKey: MemberSortKey, activeSort: MemberSortState, onSort: (key: MemberSortKey) => void, className?: string }) {
  const active = activeSort.key === sortKey

  return (
    <th className={`px-4 py-3 whitespace-nowrap ${className}`}>
      <button type="button" onClick={() => onSort(sortKey)} className={`inline-flex min-w-max items-center gap-1 font-medium whitespace-nowrap ${active ? 'text-blue-700' : 'text-text-tertiary hover:text-text-secondary'}`}>
        {label}
        <span className={`size-3 ${active ? (activeSort.direction === 'asc' ? 'i-ri-arrow-up-s-line' : 'i-ri-arrow-down-s-line') : 'i-ri-expand-up-down-line'}`} />
      </button>
    </th>
  )
}

function GroupsPanel({ groups, templateCountByGroup, saving, onEdit, onCopy, onRemove }: { groups: PermissionGroup[], templateCountByGroup: Map<string, number>, saving: boolean, onEdit: (g: PermissionGroup) => void, onCopy: (g: PermissionGroup) => void, onRemove: (g: PermissionGroup) => void }) {
  return (
    <div className="divide-y divide-divider-subtle">
      {groups.map(group => (
        <div key={group.id} className="grid grid-cols-[1fr_120px_120px_180px] items-center gap-4 px-6 py-4 hover:bg-background-default-hover max-lg:grid-cols-1">
          <div>
            <div className="font-medium">{group.name}</div>
            <div className="mt-1 text-xs text-text-tertiary">{group.description || '暂无说明'}</div>
          </div>
          <div className="text-sm">
            成员
            {group.member_count}
          </div>
          <div className="text-sm">
            模板
            {templateCountByGroup.get(group.id) ?? 0}
          </div>
          <div className="flex justify-end gap-2">
            <button className="h-8 rounded-md border border-divider-deep px-2 text-xs" onClick={() => onEdit(group)}>编辑</button>
            <button disabled={saving} className="h-8 rounded-md border border-divider-deep px-2 text-xs disabled:opacity-60" onClick={() => void onCopy(group)}>复制</button>
            <button disabled={saving} className="h-8 rounded-md border border-red-200 bg-red-50 px-2 text-xs text-red-700 disabled:opacity-60" onClick={() => void onRemove(group)}>删除</button>
          </div>
        </div>
      ))}
      {groups.length === 0 && <EmptyState text="暂无用户组" />}
    </div>
  )
}

function TemplatesPanel({ templates, saving, onEdit, onCopy, onRemove, onApply }: { templates: PermissionTemplate[], saving: boolean, onEdit: (t: PermissionTemplate) => void, onCopy: (t: PermissionTemplate) => void, onRemove: (t: PermissionTemplate) => void, onApply: (t: PermissionTemplate) => void }) {
  return (
    <div className="divide-y divide-divider-subtle">
      {templates.map(t => (
        <div key={t.id} className="grid grid-cols-[1fr_90px_90px_90px_90px_250px] items-center gap-4 px-6 py-4 hover:bg-background-default-hover max-xl:grid-cols-1">
          <div>
            <div className="font-medium">{t.name}</div>
            <div className="mt-1 text-xs text-text-tertiary">{t.description || '暂无说明'}</div>
          </div>
          <div className="text-sm">
            用户组
            {t.group_count ?? t.group_ids.length}
          </div>
          <div className="text-sm">
            成员
            {t.member_count}
          </div>
          <div className="text-sm">
            应用
            {(t.app_count ?? 0) + (t.explore_app_count ?? 0)}
          </div>
          <div className="text-sm">
            知识库
            {t.dataset_count}
          </div>
          <div className="flex justify-end gap-2">
            <button className="h-8 rounded-md border border-divider-deep px-2 text-xs" onClick={() => onEdit(t)}>编辑</button>
            <button disabled={saving} className="h-8 rounded-md border border-divider-deep px-2 text-xs disabled:opacity-60" onClick={() => void onCopy(t)}>复制</button>
            <button disabled={saving} className="h-8 rounded-md bg-components-button-primary-bg px-2 text-xs text-components-button-primary-text disabled:opacity-60" onClick={() => void onApply(t)}>同步</button>
            <button disabled={saving} className="h-8 rounded-md border border-red-200 bg-red-50 px-2 text-xs text-red-700 disabled:opacity-60" onClick={() => void onRemove(t)}>删除</button>
          </div>
        </div>
      ))}
      {templates.length === 0 && <EmptyState text="暂无权限模板" />}
    </div>
  )
}
function EffectivePermissionDetail({ isLoading, data }: { isLoading: boolean, data?: { apps: EffectivePermissionResource[], explore_apps: EffectivePermissionResource[], datasets: EffectivePermissionResource[], account: { email: string, name?: string | null, role: string } } }) {
  if (isLoading)
    return <EmptyState text="正在加载有效权限" />

  if (!data)
    return <EmptyState text="暂无有效权限数据" />

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-divider-subtle bg-background-default/50 p-4">
        <div className="text-sm font-semibold text-text-primary">{data.account.name || data.account.email}</div>
        <div className="mt-1 text-xs text-text-tertiary">
          {data.account.email}
          {' '}
          ·
          {' '}
          {data.account.role}
        </div>
      </div>
      <EffectiveResourceSection title="探索应用" resources={data.explore_apps} />
      <EffectiveResourceSection title="工作室应用" resources={data.apps} />
      <EffectiveResourceSection title="知识库" resources={data.datasets} />
    </div>
  )
}
function EffectivePanel({ members, selectedMemberId, onSelectMember, isLoading, data }: { members: Member[], selectedMemberId: string, onSelectMember: (id: string) => void, isLoading: boolean, data?: { apps: EffectivePermissionResource[], explore_apps: EffectivePermissionResource[], datasets: EffectivePermissionResource[], account: { email: string, name?: string | null, role: string } } }) {
  return (
    <div>
      <div className="border-b border-divider-subtle px-6 py-3">
        <select value={selectedMemberId} onChange={e => onSelectMember(e.target.value)} className="h-9 min-w-72 rounded-md border border-divider-deep bg-background-default px-2 text-sm">
          {members.map(member => (
            <option key={member.id} value={member.id}>
              {member.name || member.email}
              {' '}
              ·
              {' '}
              {member.email}
            </option>
          ))}
        </select>
      </div>
      {isLoading && <EmptyState text="正在加载有效权限" />}
      {!isLoading && data && (
        <div className="space-y-5 px-6 py-5">
          <div>
            <div className="text-sm font-semibold">{data.account.name || data.account.email}</div>
            <div className="mt-1 text-xs text-text-tertiary">
              {data.account.email}
              {' '}
              ·
              {' '}
              {data.account.role}
            </div>
          </div>
          <EffectiveResourceSection title="探索应用" resources={data.explore_apps} />
          <EffectiveResourceSection title="工作室应用" resources={data.apps} />
          <EffectiveResourceSection title="知识库" resources={data.datasets} />
        </div>
      )}
      {!isLoading && !data && <EmptyState text="请选择成员查看有效权限" />}
    </div>
  )
}
function EffectiveResourceSection({ title, resources }: { title: string, resources: EffectivePermissionResource[] }) {
  return (
    <section>
      <div className="mb-2 text-sm font-semibold">
        {title}
        {' '}
        (
        {resources.length}
        )
      </div>
      <div className="divide-y divide-divider-subtle rounded-md border border-divider-subtle bg-background-default">
        {resources.map(resource => (
          <div key={`${resource.resource_type}-${resource.id}`} className="px-3 py-3">
            <div className="flex justify-between gap-3">
              <div className="min-w-0 font-medium">{resource.name}</div>
              <div className="shrink-0 text-xs text-text-tertiary">{resource.mode || resource.permission || ''}</div>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {resource.sources.map(source => (
                <span key={`${source.source}-${source.source_id || ''}-${source.source_name || ''}`} className={`rounded-full px-2 py-0.5 text-xs ${sourceClassMap[source.source] || 'bg-slate-100 text-slate-600'}`}>
                  {sourceLabelMap[source.source] || source.source}
                  {source.source_name ? `：${source.source_name}` : ''}
                </span>
              ))}
            </div>
          </div>
        ))}
        {resources.length === 0 && <div className="px-3 py-8 text-center text-sm text-text-tertiary">暂无可见资源</div>}
      </div>
    </section>
  )
}
function ResourcesPanel({ resources, selectedResource, onOpenResource }: { resources: Array<{ id: string, kind: 'app' | 'explore' | 'dataset', name: string, subtitle: string }>, selectedResource: { kind: 'app' | 'explore' | 'dataset', id: string } | null, onOpenResource: (r: { kind: 'app' | 'explore' | 'dataset', id: string }) => void }) {
  const kindLabel = { app: '工作室', explore: '探索', dataset: '知识库' }
  return (
    <div className="divide-y divide-divider-subtle">
      {resources.map(resource => (
        <button key={`${resource.kind}-${resource.id}`} type="button" className={`grid w-full grid-cols-[90px_1fr] gap-4 px-6 py-4 text-left hover:bg-background-default-hover ${selectedResource?.kind === resource.kind && selectedResource.id === resource.id ? 'bg-blue-50' : ''}`} onClick={() => void onOpenResource(resource)}>
          <span className="text-xs font-medium text-blue-700">{kindLabel[resource.kind]}</span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">{resource.name}</span>
            <span className="mt-1 block text-xs text-text-tertiary">{resource.subtitle}</span>
          </span>
        </button>
      ))}
      {resources.length === 0 && <EmptyState text="暂无匹配资源" />}
    </div>
  )
}
function AuditPanel({ logs, onOpenLog }: { logs: AuditLogItem[], onOpenLog: (log: AuditLogItem) => void }) {
  return (
    <div className="divide-y divide-divider-subtle">
      {logs.map(log => (
        <button key={log.id} type="button" className="grid w-full grid-cols-[1fr_150px] gap-4 px-6 py-4 text-left hover:bg-background-default-hover max-lg:grid-cols-1" onClick={() => onOpenLog(log)}>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-text-primary">{log.action}</span>
            <span className="mt-1 block truncate text-xs text-text-tertiary">{log.account_id}</span>
          </span>
          <span className="text-xs text-text-tertiary">{fmt(log.created_at)}</span>
        </button>
      ))}
      {logs.length === 0 && <EmptyState text="暂无 RBAC 相关审计日志" />}
    </div>
  )
}
function AuditLogDetail({ log }: { log: AuditLogItem }) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-divider-subtle bg-background-default/50 p-4">
        <div className="text-sm font-semibold text-text-primary">{log.action}</div>
        <div className="mt-2 grid grid-cols-2 gap-3 text-xs text-text-tertiary">
          <div>
            <div className="font-medium text-text-secondary">操作人</div>
            <div className="mt-1 break-all">{log.account_id}</div>
          </div>
          <div>
            <div className="font-medium text-text-secondary">时间</div>
            <div className="mt-1">{fmt(log.created_at)}</div>
          </div>
          <div>
            <div className="font-medium text-text-secondary">IP</div>
            <div className="mt-1">{log.created_ip || '暂无'}</div>
          </div>
        </div>
      </div>
      <div>
        <div className="mb-2 text-xs font-medium text-text-tertiary">内容</div>
        <pre className="max-h-[520px] overflow-auto rounded-xl border border-divider-subtle bg-background-default/50 p-3 text-xs leading-5 text-text-secondary">{JSON.stringify(log.content ?? {}, null, 2)}</pre>
      </div>
    </div>
  )
}

function GroupEditor({ form, members, saving, onChange, onSave, onReset }: { form: PermissionGroupPayload & { id: string | null }, members: Member[], saving: boolean, onChange: (f: PermissionGroupPayload & { id: string | null }) => void, onSave: () => void, onReset: () => void }) {
  return (
    <div>
      <PanelHeader title={form.id ? '编辑用户组' : '新建用户组'} action="账号归属在这里维护" />
      <div className="space-y-4">
        <LabeledInput label="名称" value={form.name} placeholder="例如：A 部门" onChange={v => onChange({ ...form, name: v })} />
        <LabeledTextarea label="说明" value={form.description ?? ''} placeholder="记录部门、岗位或审批口径" onChange={v => onChange({ ...form, description: v })} />
        <MemberPicker members={members} selectedIds={form.member_ids} onToggle={id => onChange({ ...form, member_ids: toggle(form.member_ids, id) })} onChange={memberIds => onChange({ ...form, member_ids: memberIds })} />
        <EditorActions saving={saving} saveText="保存用户组" onSave={onSave} onReset={onReset} />
      </div>
    </div>
  )
}
function TemplateEditor({ form, groups, apps, exploreApps, datasets, effectiveMemberCount, saving, onChange, onSave, onReset }: { form: PermissionTemplatePayload & { id: string | null }, groups: PermissionGroup[], apps: App[], exploreApps: InstalledApp[], datasets: DataSet[], effectiveMemberCount: number, saving: boolean, onChange: (f: PermissionTemplatePayload & { id: string | null }) => void, onSave: () => void, onReset: () => void }) {
  return (
    <div>
      <PanelHeader title={form.id ? '编辑权限模板' : '新建权限模板'} action="模板绑定用户组和资源" />
      <div className="mb-4 grid grid-cols-2 gap-2 text-xs">
        <SummaryBadge label="影响成员" value={effectiveMemberCount} />
        <SummaryBadge label="探索应用" value={form.explore_app_ids.length} />
        <SummaryBadge label="工作室应用" value={form.app_ids.length} />
        <SummaryBadge label="知识库" value={form.dataset_ids.length} />
      </div>
      <div className="space-y-4">
        <LabeledInput label="名称" value={form.name} placeholder="例如：A 部门通用权限" onChange={v => onChange({ ...form, name: v })} />
        <LabeledTextarea label="说明" value={form.description ?? ''} placeholder="记录模板适用范围" onChange={v => onChange({ ...form, description: v })} />
        <PickerBlock title="适用用户组" items={groups.map(g => ({ id: g.id, title: g.name, subtitle: `${g.member_count} 个成员` }))} selectedIds={form.group_ids} onToggle={id => onChange({ ...form, group_ids: toggle(form.group_ids, id) })} onChange={groupIds => onChange({ ...form, group_ids: groupIds })} />
        <PickerBlock title="探索应用" items={exploreApps.map(item => ({ id: item.app.id, title: item.app.name, subtitle: appModeLabelMap[item.app.mode] || item.app.mode }))} selectedIds={form.explore_app_ids} onToggle={id => onChange({ ...form, explore_app_ids: toggle(form.explore_app_ids, id) })} onChange={exploreAppIds => onChange({ ...form, explore_app_ids: exploreAppIds })} />
        <PickerBlock title="工作室应用" items={apps.map(app => ({ id: app.id, title: app.name, subtitle: appModeLabelMap[app.mode] || app.mode }))} selectedIds={form.app_ids} onToggle={id => onChange({ ...form, app_ids: toggle(form.app_ids, id) })} onChange={appIds => onChange({ ...form, app_ids: appIds })} />
        <PickerBlock title="知识库" items={datasets.map(dataset => ({ id: dataset.id, title: dataset.name, subtitle: datasetPermissionLabelMap[dataset.permission] || dataset.permission }))} selectedIds={form.dataset_ids} onToggle={id => onChange({ ...form, dataset_ids: toggle(form.dataset_ids, id) })} onChange={datasetIds => onChange({ ...form, dataset_ids: datasetIds })} />
        <EditorActions saving={saving} saveText="保存模板" onSave={onSave} onReset={onReset} />
      </div>
    </div>
  )
}
function ResourceEditor({ selectedResource, members, memberIds, saving, onToggleMember, onChangeMembers, onSave }: { selectedResource: { kind: 'app' | 'explore' | 'dataset', id: string } | null, members: Member[], memberIds: string[], saving: boolean, onToggleMember: (id: string) => void, onChangeMembers: (ids: string[]) => void, onSave: () => void }) {
  if (!selectedResource)
    return <EmptyState text="请选择资源" />
  return (
    <div>
      <PanelHeader title="资源直授权" action="用于排查和临时授权" />
      <MemberPicker members={members} selectedIds={memberIds} onToggle={onToggleMember} onChange={onChangeMembers} />
      <button disabled={saving} onClick={() => void onSave()} className="mt-4 inline-flex h-9 w-full items-center justify-center rounded-md bg-components-button-primary-bg text-sm font-medium text-components-button-primary-text disabled:opacity-60">保存直授权</button>
    </div>
  )
}
function GeneralSettingsPanel({ showUnauthorizedResourceCards, loading, onToggle }: { showUnauthorizedResourceCards: boolean, loading: boolean, onToggle: () => void }) {
  return (
    <div className="p-5">
      <div className="overflow-hidden rounded-xl border border-divider-subtle bg-background-section shadow-xs">
        <div className="flex items-center justify-between gap-6 px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="flex size-8 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                <span className="i-ri-layout-grid-line size-4" aria-hidden />
              </span>
              <div>
                <div className="text-sm font-semibold text-text-primary">不可用卡片可见</div>
                <div className="mt-0.5 text-xs text-text-tertiary">仅影响工作室和知识库列表，不放宽后端权限。</div>
              </div>
            </div>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={showUnauthorizedResourceCards}
            aria-label="不可用卡片可见"
            disabled={loading}
            onClick={onToggle}
            className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-transparent transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${showUnauthorizedResourceCards ? 'bg-blue-600' : 'bg-background-default-dimmed'}`}
          >
            <span className={`inline-block size-5 rounded-full bg-white shadow transition-transform ${showUnauthorizedResourceCards ? 'translate-x-5' : 'translate-x-0.5'}`} />
          </button>
        </div>
      </div>
    </div>
  )
}
function PanelHeader({ title, action }: { title: string, action: string }) {
  return (
    <div className="mb-4 border-b border-divider-subtle pb-3">
      <div className="text-sm font-semibold text-text-primary">{title}</div>
      <div className="mt-1 text-xs text-text-tertiary">{action}</div>
    </div>
  )
}
function SummaryBadge({ label, value }: { label: string, value: string | number }) {
  return (
    <div className="rounded-lg border border-divider-subtle bg-background-default/50 px-3 py-2">
      <div className="text-base leading-5 font-semibold text-text-primary">{value}</div>
      <div className="mt-1 text-text-tertiary">{label}</div>
    </div>
  )
}
function LabeledInput({ label, value, placeholder, onChange }: { label: string, value: string, placeholder: string, onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-text-tertiary">{label}</span>
      <input value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} className="mt-1 h-9 w-full rounded-md border border-divider-deep bg-background-body px-3 text-sm outline-none focus:border-blue-400" />
    </label>
  )
}
function LabeledTextarea({ label, value, placeholder, onChange }: { label: string, value: string, placeholder: string, onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-text-tertiary">{label}</span>
      <textarea value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} className="mt-1 min-h-20 w-full resize-none rounded-md border border-divider-deep bg-background-body px-3 py-2 text-sm outline-none focus:border-blue-400" />
    </label>
  )
}
function MemberPicker({ members, selectedIds, onToggle, onChange }: { members: Member[], selectedIds: string[], onToggle: (id: string) => void, onChange: (ids: string[]) => void }) {
  return (
    <PickerBlock
      title="成员"
      items={members.map(m => ({ id: m.id, title: m.name || m.email, subtitle: `${m.email} · ${roleLabelMap[m.role]}` }))}
      selectedIds={selectedIds}
      onToggle={onToggle}
      onChange={onChange}
    />
  )
}
function PickerBlock({ title, items, selectedIds, onToggle, onChange }: { title: string, items: Array<{ id: string, title: string, subtitle: string }>, selectedIds: string[], onToggle: (id: string) => void, onChange: (ids: string[]) => void }) {
  const itemIds = items.map(item => item.id)
  const selectedSet = new Set(selectedIds)

  return (
    <details className="group rounded-md border border-divider-subtle bg-background-body">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-3 [&::-webkit-details-marker]:hidden">
        <span>
          <span className="text-sm font-medium">{title}</span>
          <span className="ml-2 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">{selectedIds.length}</span>
        </span>
        <span className="i-ri-arrow-down-s-line size-4 text-text-tertiary transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-divider-subtle">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-divider-subtle px-3 py-2">
          <span className="text-xs text-text-tertiary">
            已选
            {' '}
            {selectedIds.length}
            {' '}
            /
            {' '}
            {items.length}
          </span>
          <div className="flex items-center gap-1">
            <button type="button" disabled={items.length === 0} onClick={() => onChange(itemIds)} className="h-7 rounded-md border border-divider-deep px-2 text-xs font-medium text-text-secondary disabled:cursor-not-allowed disabled:opacity-50">全选</button>
            <button type="button" disabled={items.length === 0} onClick={() => onChange(itemIds.filter(id => !selectedSet.has(id)))} className="h-7 rounded-md border border-divider-deep px-2 text-xs font-medium text-text-secondary disabled:cursor-not-allowed disabled:opacity-50">反选</button>
            <button type="button" disabled={selectedIds.length === 0} onClick={() => onChange([])} className="h-7 rounded-md border border-divider-deep px-2 text-xs font-medium text-text-secondary disabled:cursor-not-allowed disabled:opacity-50">清空</button>
          </div>
        </div>
        <div className="max-h-64 overflow-y-auto p-2">
          {items.map(item => (
            <label key={item.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-2 hover:bg-background-default-hover">
              <input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => onToggle(item.id)} />
              <span className="min-w-0">
                <span className="block truncate text-sm">{item.title}</span>
                <span className="block truncate text-xs text-text-tertiary">{item.subtitle}</span>
              </span>
            </label>
          ))}
          {items.length === 0 && <div className="px-2 py-8 text-center text-sm text-text-tertiary">暂无数据</div>}
        </div>
      </div>
    </details>
  )
}
function EditorActions({ saving, saveText, onSave, onReset }: { saving: boolean, saveText: string, onSave: () => void, onReset: () => void }) {
  return (
    <div className="flex gap-2">
      <button disabled={saving} onClick={() => void onSave()} className="inline-flex h-9 flex-1 items-center justify-center rounded-md bg-components-button-primary-bg text-sm font-medium text-components-button-primary-text disabled:opacity-60">{saving ? '保存中...' : saveText}</button>
      <button onClick={onReset} className="inline-flex h-9 items-center justify-center rounded-md border border-divider-deep px-3 text-sm font-medium text-text-secondary">重置</button>
    </div>
  )
}
