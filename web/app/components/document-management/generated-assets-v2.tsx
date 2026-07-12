'use client'

/* eslint-disable no-alert, react/set-state-in-effect, style/max-statements-per-line */

import type { GeneratedAsset, GeneratedAssetIdentity } from '@/service/generated-files'
import { toast } from '@langgenius/dify-ui/toast'
import {
  RiCheckboxMultipleLine,
  RiCloseLine,
  RiDownload2Line,
  RiFilter3Line,
  RiGridLine,
  RiListCheck2,
  RiMore2Fill,
  RiRefreshLine,
  RiSearchLine,
  RiUserLine,
} from '@remixicon/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useDebounce } from 'ahooks'
import { useEffect, useMemo, useState } from 'react'
import DocumentOriginalPreview from '@/app/components/document-management/original-preview'
import { useAppContext } from '@/context/app-context'
import {
  deleteGeneratedAsset,
  fetchGeneratedAssetDownloadUrl,
  fetchGeneratedAssetIdentities,
  fetchGeneratedAssets,
  updateGeneratedAssetIdentities,
} from '@/service/generated-files'
import { asyncRunSafe } from '@/utils'
import { downloadUrl } from '@/utils/download'
import { getGeneratedAssetThumbnailUrl } from './generated-files'

const PAGE_SIZE = 50
const fileTypes = [
  ['', '全部类型'],
  ['image', '图片'],
  ['video', '视频'],
  ['audio', '音频'],
  ['document', '文档'],
  ['presentation', 'PPT'],
  ['spreadsheet', '表格'],
  ['archive', '压缩包'],
] as const
const fileTypeNames: Record<string, string> = Object.fromEntries(fileTypes.filter(([value]) => value))
const channelNames: Record<string, string> = {
  'console': '后台账号',
  'service-api': 'Service API',
  'web-app': 'WebApp',
  'webapp': 'WebApp',
  'feishu': '飞书',
  'openclaw': 'OpenClaw',
  'workbuddy': 'WorkBuddy',
  'mmb-enterprise-mcp': '企业 MCP',
}

const formatSize = (size?: number) => {
  if (!size || size < 0)
    return '-'
  if (size < 1024 * 1024)
    return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const formatTime = (timestamp?: number | null) => timestamp
  ? new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(timestamp * 1000))
  : '-'

const dateToTimestamp = (value: string, nextDay = false) => {
  if (!value)
    return undefined
  const date = new Date(`${value}T00:00:00`)
  if (nextDay)
    date.setDate(date.getDate() + 1)
  return Math.floor(date.getTime() / 1000)
}

const AssetThumb = ({ asset, large = false }: { asset: GeneratedAsset, large?: boolean }) => {
  const url = getGeneratedAssetThumbnailUrl(asset)
  return (
    <div className={`${large ? 'aspect-video w-full' : 'size-10'} flex shrink-0 items-center justify-center overflow-hidden rounded-lg bg-background-section text-text-quaternary`}>
      {url ? <img src={url} alt={asset.name} loading="lazy" className="h-full w-full object-cover" /> : <RiListCheck2 className="size-5" />}
    </div>
  )
}

const IdentityManager = ({ onClose }: { onClose: () => void }) => {
  const queryClient = useQueryClient()
  const [includeTest, setIncludeTest] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [targetAccount, setTargetAccount] = useState('')
  const { data, isLoading } = useQuery({
    queryKey: ['generated-asset-identities', includeTest],
    queryFn: () => fetchGeneratedAssetIdentities(includeTest),
  })
  const mutation = useMutation({
    mutationFn: updateGeneratedAssetIdentities,
    onSuccess: () => {
      setSelected([])
      queryClient.invalidateQueries({ queryKey: ['generated-asset-identities'] })
      queryClient.invalidateQueries({ queryKey: ['generated-assets-v2'] })
      toast.success('身份设置已更新')
    },
    onError: () => toast.error('身份设置更新失败'),
  })
  const apply = (payload: { account_id?: string | null, is_test?: boolean | null }) => {
    if (!selected.length)
      return
    mutation.mutate({ end_user_ids: selected, ...payload })
  }
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/35 p-4" onMouseDown={event => event.target === event.currentTarget && onClose()}>
      <section className="flex max-h-[82vh] w-full max-w-5xl flex-col overflow-hidden rounded-lg border border-divider-regular bg-background-default shadow-xl">
        <header className="flex h-14 items-center justify-between border-b border-divider-subtle px-4">
          <div>
            <div className="text-sm font-semibold text-text-primary">渠道身份管理</div>
            <div className="text-xs text-text-tertiary">绑定只影响后台聚合，不改变外部 API 权限</div>
          </div>
          <button type="button" aria-label="关闭" title="关闭" className="flex size-9 items-center justify-center rounded-lg hover:bg-state-base-hover" onClick={onClose}><RiCloseLine className="size-5" /></button>
        </header>
        <div className="flex flex-wrap items-center gap-2 border-b border-divider-subtle px-4 py-3">
          <select value={targetAccount} onChange={event => setTargetAccount(event.target.value)} className="border-components-input-border h-8 min-w-52 rounded-lg border bg-components-input-bg-normal px-2 text-sm">
            <option value="">选择要绑定的人员</option>
            {data?.accounts.map(account => (
              <option key={account.id} value={account.id}>
                {account.name}
                {' '}
                ·
                {' '}
                {account.email}
              </option>
            ))}
          </select>
          <button type="button" disabled={!selected.length || !targetAccount || mutation.isPending} className="h-8 rounded-lg bg-components-button-primary-bg px-3 text-xs font-medium text-components-button-primary-text disabled:opacity-40" onClick={() => apply({ account_id: targetAccount })}>绑定所选</button>
          <button type="button" disabled={!selected.length || mutation.isPending} className="h-8 rounded-lg border border-components-button-secondary-border px-3 text-xs disabled:opacity-40" onClick={() => apply({ account_id: null })}>解除绑定</button>
          <button type="button" disabled={!selected.length || mutation.isPending} className="h-8 rounded-lg border border-components-button-secondary-border px-3 text-xs disabled:opacity-40" onClick={() => apply({ is_test: true })}>标记测试</button>
          <button type="button" disabled={!selected.length || mutation.isPending} className="h-8 rounded-lg border border-components-button-secondary-border px-3 text-xs disabled:opacity-40" onClick={() => apply({ is_test: false })}>恢复正式</button>
          <label className="ml-auto flex items-center gap-2 text-xs text-text-secondary">
            <input type="checkbox" checked={includeTest} onChange={event => setIncludeTest(event.target.checked)} />
            包含测试身份
          </label>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {isLoading
            ? <div className="p-8 text-center text-sm text-text-tertiary">加载中...</div>
            : (
                <table className="w-full min-w-[800px] text-sm">
                  <thead className="sticky top-0 bg-background-default-subtle text-xs text-text-tertiary">
                    <tr>
                      <th className="w-12 p-3"></th>
                      <th className="p-3 text-left">渠道身份</th>
                      <th className="p-3 text-left">归属人员</th>
                      <th className="p-3 text-left">应用</th>
                      <th className="p-3 text-right">资产</th>
                      <th className="p-3 text-left">最近使用</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data?.identities.map((identity: GeneratedAssetIdentity) => (
                      <tr key={identity.id} className="border-t border-divider-subtle hover:bg-state-base-hover">
                        <td className="p-3 text-center"><input type="checkbox" checked={selected.includes(identity.id)} onChange={() => setSelected(ids => ids.includes(identity.id) ? ids.filter(id => id !== identity.id) : [...ids, identity.id])} /></td>
                        <td className="p-3">
                          <div className="font-medium text-text-primary">{identity.name}</div>
                          <div className="text-xs text-text-tertiary">
                            {channelNames[identity.channel_type] || identity.channel_type}
                            {identity.is_test ? ' · 测试' : ''}
                          </div>
                        </td>
                        <td className="p-3 text-text-secondary">{identity.account_name || '未归属'}</td>
                        <td className="max-w-60 truncate p-3 text-text-secondary" title={identity.app_names.join('、')}>{identity.app_names.join('、') || '-'}</td>
                        <td className="p-3 text-right tabular-nums">{identity.asset_count}</td>
                        <td className="p-3 text-text-tertiary">{formatTime(identity.last_used_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
        </div>
      </section>
    </div>
  )
}

const GeneratedAssetsLibraryV2 = () => {
  const queryClient = useQueryClient()
  const { isCurrentWorkspaceManager } = useAppContext()
  const [scope, setScope] = useState<'my' | 'all' | 'unassigned'>('my')
  const [view, setView] = useState<'list' | 'grid'>('list')
  const [keyword, setKeyword] = useState('')
  const debouncedKeyword = useDebounce(keyword.trim(), { wait: 350 })
  const [fileType, setFileType] = useState('')
  const [appId, setAppId] = useState('')
  const [personId, setPersonId] = useState('')
  const [channel, setChannel] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [includeTest, setIncludeTest] = useState(false)
  const [sort, setSort] = useState<'-created_at' | 'created_at'>('-created_at')
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [previewId, setPreviewId] = useState('')
  const [identityOpen, setIdentityOpen] = useState(false)

  useEffect(() => {
    const saved = window.localStorage.getItem('generated-assets-preferences-v2')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        if (parsed.view === 'grid' || parsed.view === 'list')
          setView(parsed.view)
        if (isCurrentWorkspaceManager && ['my', 'all', 'unassigned'].includes(parsed.scope))
          setScope(parsed.scope)
        if (parsed.sort === 'created_at' || parsed.sort === '-created_at')
          setSort(parsed.sort)
        setFileType(parsed.fileType || '')
        setAppId(parsed.appId || '')
        setPersonId(parsed.personId || '')
        setChannel(parsed.channel || '')
        setStartDate(parsed.startDate || '')
        setEndDate(parsed.endDate || '')
        setIncludeTest(Boolean(parsed.includeTest))
      }
      catch {}
    }
    const assetId = new URLSearchParams(window.location.search).get('generatedAssetId')
    if (assetId)
      setPreviewId(assetId)
  }, [isCurrentWorkspaceManager])

  useEffect(() => {
    window.localStorage.setItem('generated-assets-preferences-v2', JSON.stringify({ view, scope, sort, fileType, appId, personId, channel, startDate, endDate, includeTest }))
  }, [appId, channel, endDate, fileType, includeTest, personId, scope, sort, startDate, view])

  const params = useMemo(() => ({
    page,
    limit: PAGE_SIZE,
    scope,
    sort,
    include_test_data: includeTest,
    keyword: debouncedKeyword || undefined,
    file_type: fileType || undefined,
    source_app_ids: appId || undefined,
    person_ids: personId || undefined,
    channel_types: channel || undefined,
    created_after: dateToTimestamp(startDate),
    created_before: dateToTimestamp(endDate, true),
  }), [appId, channel, debouncedKeyword, endDate, fileType, includeTest, page, personId, scope, sort, startDate])
  const { data, isLoading, isFetching, refetch } = useQuery({ queryKey: ['generated-assets-v2', params], queryFn: () => fetchGeneratedAssets(params) })
  const files = data?.data || []
  const totalPages = Math.max(1, Math.ceil((data?.total || 0) / PAGE_SIZE))
  const [previewFullscreen, setPreviewFullscreen] = useState(false)
  const previewIndex = files.findIndex(file => file.id === previewId)
  const resetFilters = () => { setKeyword(''); setFileType(''); setAppId(''); setPersonId(''); setChannel(''); setStartDate(''); setEndDate(''); setIncludeTest(false); setPage(1) }
  const activeFilterCount = [fileType, appId, personId, channel, startDate, endDate, includeTest ? 'test' : ''].filter(Boolean).length
  const openPreview = (id: string) => {
    setPreviewId(id)
    const url = new URL(window.location.href)
    url.searchParams.set('generatedAssetId', id)
    window.history.replaceState({}, '', url)
  }
  const closePreview = () => {
    setPreviewId('')
    setPreviewFullscreen(false)
    const url = new URL(window.location.href)
    url.searchParams.delete('generatedAssetId')
    window.history.replaceState({}, '', url)
  }
  const download = async (asset: GeneratedAsset) => {
    const [error, response] = await asyncRunSafe(fetchGeneratedAssetDownloadUrl(asset.id))
    if (error || !response?.url)
      return toast.error('下载链接生成失败')
    downloadUrl({ url: response.url, fileName: asset.name, target: asset.storage_type === 'remote_url' ? '_blank' : undefined })
  }
  const removeMutation = useMutation({
    mutationFn: async (ids: string[]) => Promise.all(ids.map(deleteGeneratedAsset)),
    onSuccess: () => { setSelectedIds([]); queryClient.invalidateQueries({ queryKey: ['generated-assets-v2'] }); toast.success('已从资产索引移除') },
    onError: () => toast.error('移除失败'),
  })
  const remove = (ids: string[]) => {
    if (ids.length && window.confirm(`将从资产索引移除 ${ids.length} 项，不删除源文件。继续吗？`))
      removeMutation.mutate(ids)
  }
  const toggleSelected = (id: string) => setSelectedIds(ids => ids.includes(id) ? ids.filter(value => value !== id) : [...ids, id])
  const facets = data?.facets

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex rounded-lg bg-background-section p-1">
          {([['my', '我的资产'], ['all', '全租户'], ['unassigned', '未归属']] as const).filter(([value]) => value === 'my' || isCurrentWorkspaceManager).map(([value, label]) => (
            <button key={value} type="button" className={`h-8 rounded-md px-3 text-sm ${scope === value ? 'bg-background-default font-medium text-text-primary shadow-xs' : 'text-text-secondary'}`} onClick={() => { setScope(value); setPage(1); setSelectedIds([]) }}>{label}</button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {isCurrentWorkspaceManager && (
            <button type="button" className="inline-flex h-9 items-center gap-2 rounded-lg border border-components-button-secondary-border px-3 text-sm" onClick={() => setIdentityOpen(true)}>
              <RiUserLine className="size-4" />
              身份管理
            </button>
          )}
          <div className="flex rounded-lg border border-components-button-secondary-border p-0.5">
            <button type="button" title="列表视图" aria-label="列表视图" className={`flex size-8 items-center justify-center rounded-md ${view === 'list' ? 'bg-background-section' : ''}`} onClick={() => setView('list')}><RiListCheck2 className="size-4" /></button>
            <button type="button" title="网格视图" aria-label="网格视图" className={`flex size-8 items-center justify-center rounded-md ${view === 'grid' ? 'bg-background-section' : ''}`} onClick={() => setView('grid')}><RiGridLine className="size-4" /></button>
          </div>
        </div>
      </div>

      <section className="rounded-lg border border-divider-subtle bg-background-default">
        <div className="flex flex-wrap items-center gap-2 p-3">
          <div className="relative min-w-60 flex-1">
            <RiSearchLine className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-quaternary" />
            <input value={keyword} onChange={(event) => { setKeyword(event.target.value); setPage(1) }} placeholder="搜索文件名或应用" className="h-9 w-full rounded-lg bg-components-input-bg-normal pr-3 pl-8 text-sm outline-none" />
          </div>
          <select
            value={fileType}
            onChange={(event) => {
              setFileType(event.target.value); setPage(1); if (['image', 'video'].includes(event.target.value))
                setView('grid')
            }}
            className="border-components-input-border h-9 rounded-lg border bg-components-input-bg-normal px-2 text-sm"
          >
            {fileTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <select value={appId} onChange={(event) => { setAppId(event.target.value); setPage(1) }} className="border-components-input-border h-9 max-w-48 rounded-lg border bg-components-input-bg-normal px-2 text-sm">
            <option value="">全部应用</option>
            {facets?.apps.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select aria-label="人员" value={personId} onChange={(event) => { setPersonId(event.target.value); setPage(1) }} className="border-components-input-border h-9 max-w-44 rounded-lg border bg-components-input-bg-normal px-2 text-sm">
            <option value="">全部人员</option>
            {facets?.people?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select aria-label="渠道" value={channel} onChange={(event) => { setChannel(event.target.value); setPage(1) }} className="border-components-input-border h-9 max-w-44 rounded-lg border bg-components-input-bg-normal px-2 text-sm">
            <option value="">全部渠道</option>
            {facets?.channels?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <input aria-label="开始日期" type="date" value={startDate} onChange={(event) => { setStartDate(event.target.value); setPage(1) }} className="border-components-input-border h-9 rounded-lg border bg-components-input-bg-normal px-2 text-xs" />
          <input aria-label="结束日期" type="date" value={endDate} onChange={(event) => { setEndDate(event.target.value); setPage(1) }} className="border-components-input-border h-9 rounded-lg border bg-components-input-bg-normal px-2 text-xs" />
          <select aria-label="排序" value={sort} onChange={event => setSort(event.target.value as typeof sort)} className="border-components-input-border h-9 rounded-lg border bg-components-input-bg-normal px-2 text-sm">
            <option value="-created_at">最新生成</option>
            <option value="created_at">最早生成</option>
          </select>
          <button type="button" title="刷新" aria-label="刷新" disabled={isFetching} className="flex size-9 items-center justify-center rounded-lg border border-components-button-secondary-border disabled:opacity-40" onClick={() => refetch()}><RiRefreshLine className={`size-4 ${isFetching ? 'animate-spin' : ''}`} /></button>
        </div>
        <div className="flex min-h-10 flex-wrap items-center gap-2 border-t border-divider-subtle px-3 py-2 text-xs">
          <RiFilter3Line className="size-4 text-text-tertiary" />
          {activeFilterCount === 0
            ? <span className="text-text-tertiary">未设置筛选</span>
            : (
                <>
                  {fileType && (
                    <button type="button" className="rounded-md bg-background-section px-2 py-1" onClick={() => setFileType('')}>
                      {fileTypeNames[fileType]}
                      {' '}
                      ×
                    </button>
                  )}
                  {appId && (
                    <button type="button" className="rounded-md bg-background-section px-2 py-1" onClick={() => setAppId('')}>
                      应用：
                      {facets?.apps.find(item => item.id === appId)?.name}
                      {' '}
                      ×
                    </button>
                  )}
                  {personId && (
                    <button type="button" className="rounded-md bg-background-section px-2 py-1" onClick={() => setPersonId('')}>
                      人员：
                      {facets?.people?.find(item => item.id === personId)?.name}
                      {' '}
                      ×
                    </button>
                  )}
                  {channel && (
                    <button type="button" className="rounded-md bg-background-section px-2 py-1" onClick={() => setChannel('')}>
                      渠道：
                      {facets?.channels?.find(item => item.id === channel)?.name}
                      {' '}
                      ×
                    </button>
                  )}
                  {(startDate || endDate) && (
                    <button type="button" className="rounded-md bg-background-section px-2 py-1" onClick={() => { setStartDate(''); setEndDate('') }}>
                      时间：
                      {startDate || '不限'}
                      {' '}
                      至
                      {endDate || '不限'}
                      {' '}
                      ×
                    </button>
                  )}
                  <button type="button" className="text-components-button-primary-bg" onClick={resetFilters}>
                    重置全部 (
                    {activeFilterCount}
                    )
                  </button>
                </>
              )}
          <label className="ml-auto flex items-center gap-2 text-text-secondary">
            <input type="checkbox" checked={includeTest} onChange={(event) => { setIncludeTest(event.target.checked); setPage(1) }} />
            包含测试数据
          </label>
        </div>
      </section>

      {selectedIds.length > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-divider-subtle bg-background-default px-3 py-2 text-sm">
          <RiCheckboxMultipleLine className="size-4" />
          <span>
            已选择
            {selectedIds.length}
            {' '}
            项
          </span>
          <button type="button" className="ml-auto h-8 rounded-lg border px-3 text-xs" onClick={() => files.filter(file => selectedIds.includes(file.id)).forEach(download)}>批量下载</button>
          <button type="button" className="h-8 rounded-lg px-3 text-xs text-text-destructive" onClick={() => remove(selectedIds)}>移除索引</button>
        </div>
      )}

      <main className="min-h-0 flex-1 overflow-auto rounded-lg border border-divider-subtle bg-background-default">
        {isLoading
          ? <div className="flex h-full items-center justify-center text-sm text-text-tertiary">加载中...</div>
          : files.length === 0
            ? <div className="flex h-full items-center justify-center text-sm text-text-tertiary">当前范围暂无资产</div>
            : view === 'grid'
              ? (
                  <div className="grid grid-cols-2 gap-3 p-3 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                    {files.map(file => (
                      <article key={file.id} className="group relative overflow-hidden rounded-lg border border-divider-subtle bg-background-default hover:border-divider-regular" onClick={() => openPreview(file.id)}>
                        <div className="absolute top-2 left-2 z-10" onClick={event => event.stopPropagation()}><input type="checkbox" aria-label={`选择 ${file.name}`} checked={selectedIds.includes(file.id)} onChange={() => toggleSelected(file.id)} /></div>
                        <AssetThumb asset={file} large />
                        <div className="p-3">
                          <div className="truncate text-sm font-medium text-text-primary" title={file.name}>{file.name}</div>
                          <div className="mt-1 flex items-center justify-between gap-2 text-xs text-text-tertiary">
                            <span>{fileTypeNames[file.file_type] || file.file_type}</span>
                            <span>{formatTime(file.created_at)}</span>
                          </div>
                          <div className="mt-1 truncate text-xs text-text-tertiary">
                            {file.person_name || '未归属'}
                            {' '}
                            ·
                            {' '}
                            {channelNames[file.channel_type || 'console'] || file.channel_type}
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                )
              : (
                  <table className="w-full min-w-[1050px] table-fixed text-sm">
                    <thead className="sticky top-0 z-10 bg-background-default-subtle text-xs text-text-tertiary">
                      <tr>
                        <th className="w-12 p-3"></th>
                        <th className="w-[320px] p-3 text-left">内容</th>
                        <th className="w-28 p-3 text-left">类型</th>
                        <th className="w-40 p-3 text-left">人员</th>
                        <th className="w-44 p-3 text-left">渠道身份</th>
                        <th className="w-48 p-3 text-left">应用</th>
                        <th className="w-24 p-3 text-right">大小</th>
                        <th className="w-36 p-3 text-left">生成时间</th>
                        <th className="w-20 p-3"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {files.map(file => (
                        <tr key={file.id} className="border-t border-divider-subtle hover:bg-state-base-hover" onClick={() => openPreview(file.id)}>
                          <td className="p-3 text-center" onClick={event => event.stopPropagation()}><input type="checkbox" aria-label={`选择 ${file.name}`} checked={selectedIds.includes(file.id)} onChange={() => toggleSelected(file.id)} /></td>
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              <AssetThumb asset={file} />
                              <div className="min-w-0">
                                <div className="truncate font-medium text-text-primary" title={file.name}>{file.name}</div>
                                <div className="text-xs text-text-tertiary">
                                  .
                                  {file.extension}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="p-3 text-text-secondary">{fileTypeNames[file.file_type] || file.file_type}</td>
                          <td className="truncate p-3 text-text-secondary" title={file.person_name || ''}>{file.person_name || '未归属'}</td>
                          <td className="p-3">
                            <div className="truncate text-text-secondary" title={file.identity_name || ''}>{file.identity_name || '后台账号'}</div>
                            <div className="text-xs text-text-tertiary">{channelNames[file.channel_type || 'console'] || file.channel_type}</div>
                          </td>
                          <td className="truncate p-3 text-text-secondary">{file.source_app_name || '未知应用'}</td>
                          <td className="p-3 text-right text-text-secondary">{formatSize(file.size)}</td>
                          <td className="p-3 text-text-tertiary">{formatTime(file.created_at)}</td>
                          <td className="p-3" onClick={event => event.stopPropagation()}>
                            <div className="flex items-center">
                              <button type="button" aria-label={`下载 ${file.name}`} title="下载" className="flex size-8 items-center justify-center rounded-lg hover:bg-state-base-hover" onClick={() => download(file)}><RiDownload2Line className="size-4" /></button>
                              <details className="relative">
                                <summary aria-label="更多操作" title="更多操作" className="flex size-8 list-none items-center justify-center rounded-lg hover:bg-state-base-hover"><RiMore2Fill className="size-4" /></summary>
                                <div className="absolute right-0 z-20 mt-1 w-28 rounded-lg border border-divider-regular bg-background-default p-1 shadow-lg"><button type="button" className="h-8 w-full rounded-md px-2 text-left text-xs text-text-destructive hover:bg-state-destructive-hover" onClick={() => remove([file.id])}>移除索引</button></div>
                              </details>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
      </main>
      <footer className="flex h-11 items-center justify-between text-xs text-text-tertiary">
        <span>
          共
          {data?.total || 0}
          {' '}
          项 · 第
          {page}
          /
          {totalPages}
          {' '}
          页
        </span>
        <div className="flex gap-2">
          <button type="button" disabled={page <= 1 || isFetching} className="h-8 rounded-lg border px-3 disabled:opacity-40" onClick={() => setPage(value => value - 1)}>上一页</button>
          <button type="button" disabled={page >= totalPages || isFetching} className="h-8 rounded-lg border px-3 disabled:opacity-40" onClick={() => setPage(value => value + 1)}>下一页</button>
        </div>
      </footer>

      {previewId && <div className="fixed inset-0 z-[60] bg-black/30" onMouseDown={event => event.target === event.currentTarget && closePreview()}><aside className={`absolute inset-y-0 right-0 w-full bg-background-body shadow-2xl ${previewFullscreen ? '' : 'md:w-[82vw] xl:w-[72vw]'}`}><DocumentOriginalPreview generatedAssetId={previewId} onClose={closePreview} onPrevious={() => previewIndex > 0 && openPreview(files[previewIndex - 1].id)} onNext={() => previewIndex >= 0 && previewIndex < files.length - 1 && openPreview(files[previewIndex + 1].id)} onToggleFullscreen={() => setPreviewFullscreen(value => !value)} isFullscreen={previewFullscreen} hasPrevious={previewIndex > 0} hasNext={previewIndex >= 0 && previewIndex < files.length - 1} /></aside></div>}
      {identityOpen && <IdentityManager onClose={() => setIdentityOpen(false)} />}
    </div>
  )
}

export default GeneratedAssetsLibraryV2
