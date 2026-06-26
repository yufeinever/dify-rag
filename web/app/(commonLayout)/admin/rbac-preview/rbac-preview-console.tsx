'use client'

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
import { applyPermissionTemplate, createPermissionGroup, createPermissionTemplate, deletePermissionGroup, deletePermissionTemplate, fetchAdminAuditLogs, fetchAppList, fetchAppPermissionMembers, fetchEffectivePermissions, fetchExploreAppPermissionMembers, fetchPermissionGroups, fetchPermissionTemplates, updateAppPermissionMembers, updateExploreAppPermissionMembers, updatePermissionGroup, updatePermissionTemplate } from '@/service/apps'
import { fetchDatasets, updateDatasetSetting } from '@/service/datasets'
import { fetchInstalledAppList } from '@/service/explore'
import { useMembers, useWorkspaces } from '@/service/use-common'

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
]

const emptyGroup = { id: null, name: '', description: '', member_ids: [] } satisfies PermissionGroupPayload & { id: string | null }
const emptyTemplate = { id: null, name: '', description: '', member_ids: [], group_ids: [], app_ids: [], dataset_ids: [], explore_app_ids: [] } satisfies PermissionTemplatePayload & { id: string | null }
const toggle = (list: string[], id: string) => list.includes(id) ? list.filter(item => item !== id) : [...list, id]
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
  const [batchGroupId, setBatchGroupId] = useState('')
  const [groupForm, setGroupForm] = useState<PermissionGroupPayload & { id: string | null }>(emptyGroup)
  const [templateForm, setTemplateForm] = useState<PermissionTemplatePayload & { id: string | null }>(emptyTemplate)
  const [effectiveMemberId, setEffectiveMemberId] = useState('')
  const [selectedResource, setSelectedResource] = useState<{ kind: 'app' | 'explore' | 'dataset', id: string } | null>(null)
  const [resourceMemberIds, setResourceMemberIds] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const { currentWorkspace, isCurrentWorkspaceManager, canAny } = useAppContext()
  const hasAnyPermission = canAny ?? (() => false)
  const canEnterAdmin = hasAnyPermission(['workspace.member.view', 'workspace.member.manage']) || isCurrentWorkspaceManager
  const { data: membersData, isLoading: membersLoading, refetch: refetchMembers } = useMembers()
  const { data: workspacesData } = useWorkspaces()
  const members = useMemo(() => membersData?.accounts ?? [], [membersData?.accounts])
  const workspaces = useMemo(() => workspacesData?.workspaces ?? [], [workspacesData?.workspaces])
  const appsQuery = useQuery({ queryKey: ['rbac-preview', 'apps'], queryFn: () => fetchAppList({ url: '/apps', params: { page: 1, limit: 100 } }), enabled: canEnterAdmin })
  const exploreQuery = useQuery({ queryKey: ['rbac-preview', 'explore-apps'], queryFn: () => fetchInstalledAppList(), enabled: canEnterAdmin })
  const datasetsQuery = useQuery({ queryKey: ['rbac-preview', 'datasets'], queryFn: () => fetchDatasets({ url: '/datasets', params: { page: 1, limit: 100 } }), enabled: canEnterAdmin })
  const groupsQuery = useQuery({ queryKey: ['rbac-preview', 'groups'], queryFn: fetchPermissionGroups, enabled: canEnterAdmin })
  const templatesQuery = useQuery({ queryKey: ['rbac-preview', 'templates'], queryFn: fetchPermissionTemplates, enabled: canEnterAdmin })
  const auditQuery = useQuery({ queryKey: ['rbac-preview', 'audit'], queryFn: fetchAdminAuditLogs, enabled: canEnterAdmin })
  const activeEffectiveMemberId = effectiveMemberId || members[0]?.id || ''
  const effectiveQuery = useQuery({ queryKey: ['rbac-preview', 'effective', activeEffectiveMemberId], queryFn: () => fetchEffectivePermissions(activeEffectiveMemberId), enabled: canEnterAdmin && activeTab === 'effective' && !!activeEffectiveMemberId })
  const apps = useMemo(() => appsQuery.data?.data ?? [], [appsQuery.data?.data])
  const exploreApps = useMemo(() => exploreQuery.data?.installed_apps ?? [], [exploreQuery.data?.installed_apps])
  const datasets = useMemo(() => datasetsQuery.data?.data ?? [], [datasetsQuery.data?.data])
  const groups = useMemo(() => groupsQuery.data?.data ?? [], [groupsQuery.data?.data])
  const templates = useMemo(() => templatesQuery.data?.data ?? [], [templatesQuery.data?.data])
  const auditLogs = useMemo(() => auditQuery.data?.data ?? [], [auditQuery.data?.data])
  const currentTab = tabs.find(tab => tab.key === activeTab) ?? tabs[0]!
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
      && match(keyword, [member.name, member.email, roleLabelMap[member.role], statusLabelMap[member.status], ...memberGroups.map(group => group.name)])
  }), [groupsByMember, keyword, members, roleFilter, statusFilter])
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
      if (groupForm.id === group.id)
        setGroupForm(emptyGroup)
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
      if (templateForm.id === template.id)
        setTemplateForm(emptyTemplate)
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
      toast.success('资源直授权已保存')
    }
    finally { setSaving(false) }
  }

  if (!canEnterAdmin)
    return <div className="flex h-full items-center justify-center bg-background-body text-sm text-text-tertiary">当前账号没有进入企业权限后台的权限。</div>

  return (
    <div className="min-h-screen bg-background-body text-text-primary">
      <div className="sticky top-0 z-10 border-b border-divider-subtle bg-background-body/95 backdrop-blur">
        <div className="flex items-center justify-between gap-4 px-6 py-4">
          <div>
            <div className="text-xs font-semibold text-text-tertiary uppercase">
              MMB Enterprise RBAC Preview
              <span className="ml-2 rounded bg-blue-50 px-1.5 py-0.5 text-blue-700">预览版</span>
            </div>
            <h1 className="mt-1 text-2xl font-semibold">企业权限控制台</h1>
            <p className="mt-1 text-sm text-text-tertiary">
              当前工作区：
              {currentWorkspace?.name || '暂无'}
              。布局借鉴企业 IAM 后台，视觉保持 Dify 风格。
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button type="button" onClick={() => void refreshAll()} className="inline-flex h-9 items-center gap-2 rounded-md border border-divider-deep bg-background-default px-3 text-sm font-medium text-text-secondary hover:bg-background-default-hover">
              <span className="i-ri-refresh-line size-4" />
              刷新
            </button>
            <Link href="/apps" className="inline-flex h-9 items-center gap-2 rounded-md bg-components-button-primary-bg px-3 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover">
              <span className="i-ri-apps-2-line size-4" />
              返回 AI 中台
            </Link>
          </div>
        </div>
        <div className="grid grid-cols-5 border-t border-divider-subtle max-lg:grid-cols-2">
          <Metric label="成员" value={members.length} hint="当前工作区账号" />
          <Metric label="用户组" value={groups.length} hint="部门/岗位/项目组" />
          <Metric label="模板" value={templates.length} hint="批量授权策略" />
          <Metric label="应用" value={apps.length + exploreApps.length} hint="探索 + 工作室" />
          <Metric label="知识库" value={datasets.length} hint="可管理知识库" />
        </div>
      </div>
      <div className="grid grid-cols-[260px_1fr_360px] max-2xl:grid-cols-[240px_1fr] max-xl:grid-cols-1">
        <aside className="border-r border-divider-subtle bg-background-default px-4 py-5 max-xl:border-r-0 max-xl:border-b">
          <div className="relative mb-4">
            <span className="absolute top-1/2 left-3 i-ri-search-line size-4 -translate-y-1/2 text-text-quaternary" />
            <input value={keyword} onChange={event => setKeyword(event.target.value)} placeholder="搜索成员、用户组、模板或资源" className="h-9 w-full rounded-md border border-divider-deep bg-background-body pr-3 pl-9 text-sm outline-none focus:border-blue-400" />
          </div>
          <nav className="space-y-1">
            {tabs.map(tab => (
              <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)} className={`flex w-full items-start gap-3 rounded-md px-3 py-3 text-left transition-colors ${activeTab === tab.key ? 'bg-blue-50 text-blue-700' : 'text-text-secondary hover:bg-background-default-hover'}`}>
                <span className={`${tab.icon} mt-0.5 size-4 shrink-0`} />
                <span>
                  <span className="block text-sm font-medium">{tab.label}</span>
                  <span className="mt-0.5 block text-xs text-text-tertiary">{tab.desc}</span>
                </span>
              </button>
            ))}
          </nav>
          <div className="mt-6 rounded-md border border-divider-subtle bg-background-body p-3 text-xs leading-5 text-text-tertiary">
            <div className="font-medium text-text-secondary">融合策略</div>
            不引入 Keycloak/Casdoor 依赖，只借鉴信息架构。
          </div>
        </aside>
        <main className="min-w-0 border-r border-divider-subtle bg-background-body max-2xl:border-r-0">
          <SectionTitle title={currentTab.label} description={currentTab.desc} />
          {activeTab === 'members' && (
            <MembersPanel
              members={filteredMembers}
              groupsByMember={groupsByMember}
              selectedMemberIds={selectedMemberIds}
              roleFilter={roleFilter}
              statusFilter={statusFilter}
              batchGroupId={batchGroupId}
              groups={groups}
              isLoading={membersLoading}
              saving={saving}
              onRoleFilterChange={setRoleFilter}
              onStatusFilterChange={setStatusFilter}
              onBatchGroupChange={setBatchGroupId}
              onToggleMember={id => setSelectedMemberIds(current => toggle(current, id))}
              onToggleAll={() => setSelectedMemberIds(current => current.length === filteredMembers.length ? [] : filteredMembers.map(member => member.id))}
              onBatchUpdate={batchUpdateGroup}
              onOpenEffective={(id) => {
                setEffectiveMemberId(id)
                setActiveTab('effective')
              }}
            />
          )}
          {activeTab === 'groups' && <GroupsPanel groups={filteredGroups} templateCountByGroup={templateCountByGroup} saving={saving} onEdit={group => setGroupForm({ id: group.id, name: group.name, description: group.description ?? '', member_ids: group.member_ids })} onCopy={copyGroup} onRemove={removeGroup} />}
          {activeTab === 'templates' && <TemplatesPanel templates={filteredTemplates} saving={saving} onEdit={editTemplate} onCopy={copyTemplate} onRemove={removeTemplate} onApply={syncTemplate} />}
          {activeTab === 'effective' && <EffectivePanel members={members} selectedMemberId={activeEffectiveMemberId} onSelectMember={setEffectiveMemberId} isLoading={effectiveQuery.isLoading} data={effectiveQuery.data?.data} />}
          {activeTab === 'resources' && <ResourcesPanel resources={resources} selectedResource={selectedResource} onOpenResource={openResource} />}
          {activeTab === 'audit' && <AuditPanel logs={filteredAuditLogs} />}
        </main>
        <aside className="bg-background-default px-5 py-5 max-2xl:col-span-2 max-xl:col-span-1">
          {activeTab === 'groups' && <GroupEditor form={groupForm} members={members} saving={saving} onChange={setGroupForm} onSave={saveGroup} onReset={() => setGroupForm(emptyGroup)} />}
          {activeTab === 'templates' && <TemplateEditor form={templateForm} groups={groups} apps={apps} exploreApps={exploreApps} datasets={datasets} effectiveMemberCount={templateEffectiveMembers} saving={saving} onChange={setTemplateForm} onSave={saveTemplate} onReset={() => setTemplateForm(emptyTemplate)} />}
          {activeTab === 'resources' && <ResourceEditor selectedResource={selectedResource} members={members} memberIds={resourceMemberIds} saving={saving} onToggleMember={id => setResourceMemberIds(current => toggle(current, id))} onChangeMembers={setResourceMemberIds} onSave={saveResourceMembers} />}
          {activeTab !== 'groups' && activeTab !== 'templates' && activeTab !== 'resources' && <ContextPanel activeTab={activeTab} groups={groups.length} templates={templates.length} workspaces={workspaces.length} />}
        </aside>
      </div>
    </div>
  )
}

function Metric({ label, value, hint }: { label: string, value: string | number, hint: string }) {
  return (
    <div className="border-r border-divider-subtle px-5 py-3 last:border-r-0">
      <div className="text-xl font-semibold">{value}</div>
      <div className="mt-0.5 text-xs font-medium text-text-secondary">{label}</div>
      <div className="mt-0.5 text-xs text-text-tertiary">{hint}</div>
    </div>
  )
}
function SectionTitle({ title, description }: { title: string, description: string }) {
  return (
    <div className="border-b border-divider-subtle px-6 py-5">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-text-tertiary">{description}</p>
    </div>
  )
}
function EmptyState({ text }: { text: string }) {
  return <div className="flex h-40 items-center justify-center text-sm text-text-tertiary">{text}</div>
}

function MembersPanel({ members, groupsByMember, selectedMemberIds, roleFilter, statusFilter, batchGroupId, groups, isLoading, saving, onRoleFilterChange, onStatusFilterChange, onBatchGroupChange, onToggleMember, onToggleAll, onBatchUpdate, onOpenEffective }: { members: Member[], groupsByMember: Map<string, PermissionGroup[]>, selectedMemberIds: string[], roleFilter: string, statusFilter: string, batchGroupId: string, groups: PermissionGroup[], isLoading: boolean, saving: boolean, onRoleFilterChange: (v: string) => void, onStatusFilterChange: (v: string) => void, onBatchGroupChange: (v: string) => void, onToggleMember: (id: string) => void, onToggleAll: () => void, onBatchUpdate: (mode: 'add' | 'remove') => void, onOpenEffective: (id: string) => void }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 border-b border-divider-subtle px-6 py-3">
        <select value={roleFilter} onChange={e => onRoleFilterChange(e.target.value)} className="h-8 rounded-md border border-divider-deep bg-background-default px-2 text-xs">
          <option value="all">全部角色</option>
          {Object.entries(roleLabelMap).map(([role, label]) => <option key={role} value={role}>{label}</option>)}
        </select>
        <select value={statusFilter} onChange={e => onStatusFilterChange(e.target.value)} className="h-8 rounded-md border border-divider-deep bg-background-default px-2 text-xs">
          <option value="all">全部状态</option>
          {Object.entries(statusLabelMap).map(([status, label]) => <option key={status} value={status}>{label}</option>)}
        </select>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <span className="text-xs text-text-tertiary">
            已选
            {selectedMemberIds.length}
            {' '}
            人
          </span>
          <select value={batchGroupId} onChange={e => onBatchGroupChange(e.target.value)} className="h-8 rounded-md border border-divider-deep bg-background-default px-2 text-xs">
            <option value="">选择用户组</option>
            {groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}
          </select>
          <button disabled={saving} onClick={() => onBatchUpdate('add')} className="h-8 rounded-md bg-components-button-primary-bg px-2 text-xs font-medium text-components-button-primary-text disabled:opacity-60">加入组</button>
          <button disabled={saving} onClick={() => onBatchUpdate('remove')} className="h-8 rounded-md border border-divider-deep px-2 text-xs disabled:opacity-60">移出组</button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="bg-background-default text-xs text-text-tertiary">
            <tr>
              <th className="px-6 py-3"><input type="checkbox" checked={members.length > 0 && selectedMemberIds.length === members.length} onChange={onToggleAll} /></th>
              <th className="px-4 py-3">账号</th>
              <th className="px-4 py-3">角色</th>
              <th className="px-4 py-3">状态</th>
              <th className="px-4 py-3">用户组</th>
              <th className="px-4 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-divider-subtle">
            {members.map(member => (
              <tr key={member.id} className="hover:bg-background-default-hover">
                <td className="px-6 py-4"><input type="checkbox" checked={selectedMemberIds.includes(member.id)} onChange={() => onToggleMember(member.id)} /></td>
                <td className="px-4 py-4">
                  <div className="font-medium">{member.name || '未命名账号'}</div>
                  <div className="mt-1 text-xs text-text-tertiary">{member.email}</div>
                </td>
                <td className="px-4 py-4">{roleLabelMap[member.role]}</td>
                <td className="px-4 py-4">{statusLabelMap[member.status]}</td>
                <td className="px-4 py-4">{(groupsByMember.get(member.id) ?? []).map(group => group.name).join('、') || '未入组'}</td>
                <td className="px-4 py-4 text-right"><button className="text-xs font-medium text-blue-600" onClick={() => onOpenEffective(member.id)}>查看有效权限</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!isLoading && members.length === 0 && <EmptyState text="没有匹配的成员" />}
    </div>
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
function AuditPanel({ logs }: { logs: AuditLogItem[] }) {
  return (
    <div className="divide-y divide-divider-subtle">
      {logs.map(log => (
        <div key={log.id} className="px-6 py-4">
          <div className="flex justify-between gap-3">
            <div className="font-medium">{log.action}</div>
            <div className="text-xs text-text-tertiary">{fmt(log.created_at)}</div>
          </div>
          <pre className="mt-2 max-h-24 overflow-auto rounded bg-background-default p-2 text-xs text-text-tertiary">{JSON.stringify(log.content ?? {}, null, 2)}</pre>
        </div>
      ))}
      {logs.length === 0 && <EmptyState text="暂无 RBAC 相关审计日志" />}
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
    return <ContextPanel activeTab="resources" groups={0} templates={0} workspaces={0} />
  return (
    <div>
      <PanelHeader title="资源直授权" action="用于排查和临时授权" />
      <MemberPicker members={members} selectedIds={memberIds} onToggle={onToggleMember} onChange={onChangeMembers} />
      <button disabled={saving} onClick={() => void onSave()} className="mt-4 inline-flex h-9 w-full items-center justify-center rounded-md bg-components-button-primary-bg text-sm font-medium text-components-button-primary-text disabled:opacity-60">保存直授权</button>
    </div>
  )
}
function ContextPanel({ activeTab, groups, templates, workspaces }: { activeTab: RbacPreviewTab, groups: number, templates: number, workspaces: number }) {
  const copy: Record<RbacPreviewTab, string> = { members: '成员目录用于管理账号和用户组归属。批量操作会直接更新选中的用户组。', groups: '用户组编辑器会在本区域出现。', templates: '模板编辑器会在本区域出现。', effective: '有效权限用于解释账号最终能看到哪些资源，以及权限来源。', resources: '选择左侧资源后，可在这里维护直授权成员。', audit: '审计日志展示权限相关操作，便于回溯配置变化。' }
  return (
    <div>
      <PanelHeader title="上下文" action="操作说明" />
      <div className="rounded-md border border-divider-subtle bg-background-body p-4 text-sm leading-6 text-text-secondary">{copy[activeTab]}</div>
      <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
        <SummaryBadge label="用户组" value={groups} />
        <SummaryBadge label="模板" value={templates} />
        <SummaryBadge label="工作区" value={workspaces} />
      </div>
    </div>
  )
}
function PanelHeader({ title, action }: { title: string, action: string }) {
  return (
    <div className="mb-4 border-b border-divider-subtle pb-4">
      <div className="text-base font-semibold">{title}</div>
      <div className="mt-1 text-xs text-text-tertiary">{action}</div>
    </div>
  )
}
function SummaryBadge({ label, value }: { label: string, value: string | number }) {
  return (
    <div className="rounded-md border border-divider-subtle bg-background-body px-3 py-2">
      <div className="text-base font-semibold">{value}</div>
      <div className="mt-0.5 text-text-tertiary">{label}</div>
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
