'use client'

import type { GeneratedAsset, GeneratedAssetFacet } from '@/service/generated-files'
import { toast } from '@langgenius/dify-ui/toast'
import {
  RiApps2Line,
  RiArrowLeftSLine,
  RiArrowRightSLine,
  RiDownload2Line,
  RiFileList3Line,
  RiRefreshLine,
  RiSearchLine,
  RiUser3Line,
} from '@remixicon/react'
import { useDebounce } from 'ahooks'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { deleteGeneratedAsset, fetchGeneratedAssetDownloadUrl, fetchGeneratedAssets } from '@/service/generated-files'
import { asyncRunSafe } from '@/utils'
import { downloadUrl } from '@/utils/download'

const fileTypeOptions = [
  { value: 'all', label: '全部类型' },
  { value: 'image', label: '图片' },
  { value: 'video', label: '视频' },
  { value: 'audio', label: '音频' },
  { value: 'document', label: '文档' },
  { value: 'presentation', label: 'PPT' },
  { value: 'spreadsheet', label: '表格' },
  { value: 'archive', label: '压缩包' },
  { value: 'other', label: '其他' },
]

const fileTypeLabel: Record<string, string> = {
  image: '图片',
  document: '文档',
  presentation: 'PPT',
  spreadsheet: '表格',
  archive: '压缩包',
  audio: '音频',
  video: '视频',
  other: '其他',
}

const sourceKindOptions = [
  { value: 'all', label: '全部来源' },
  { value: 'workflow_video', label: '视频工作流' },
  { value: 'workflow_poster', label: '海报工作流' },
  { value: 'workflow_tool_file', label: '工作流文件' },
  { value: 'ppt_artifact', label: 'PPT 产物' },
  { value: 'tool_file', label: '工具文件' },
  { value: 'message_file', label: '对话文件' },
]

const sourceKindLabel: Record<string, string> = {
  workflow_video: '视频工作流',
  workflow_poster: '海报工作流',
  workflow_tool_file: '工作流文件',
  ppt_artifact: 'PPT 产物',
  tool_file: '工具文件',
  message_file: '对话文件',
}

const PAGE_SIZE = 50

const formatTime = (timestamp?: number | null) => {
  if (!timestamp)
    return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp * 1000))
}

const formatSize = (size?: number) => {
  if (!size || size < 0)
    return '-'
  if (size < 1024)
    return `${size} B`
  if (size < 1024 * 1024)
    return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024)
    return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`
}

const dateToTimestamp = (value: string, nextDay = false) => {
  if (!value)
    return undefined
  const date = new Date(`${value}T00:00:00`)
  if (nextDay)
    date.setDate(date.getDate() + 1)
  return Math.floor(date.getTime() / 1000)
}

const isPreviewable = (asset: GeneratedAsset) => !['unsupported', 'unavailable'].includes(asset.preview_kind)
  && !!(asset.preview_url || asset.source_url)

export const getGeneratedAssetThumbnailUrl = (asset: GeneratedAsset) => {
  const candidate = asset.file_type === 'video'
    ? asset.thumbnail_url
    : asset.thumbnail_url || (asset.file_type === 'image' ? asset.preview_url : '')
  if (!candidate || /\.(?:m4v|mov|mp4|webm)(?:\?|$)/i.test(candidate))
    return ''
  return candidate
}

const GeneratedAssetIcon = ({ asset }: { asset: GeneratedAsset }) => {
  const [thumbnailFailed, setThumbnailFailed] = useState(false)
  const thumbnailUrl = getGeneratedAssetThumbnailUrl(asset)
  if (thumbnailUrl && !thumbnailFailed) {
    return (
      <div className="flex size-10 shrink-0 overflow-hidden rounded-lg border border-divider-subtle bg-background-section">
        <img
          src={thumbnailUrl}
          alt={asset.name}
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => setThumbnailFailed(true)}
        />
      </div>
    )
  }

  return (
    <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-background-section text-text-tertiary">
      <RiFileList3Line className="size-5" />
    </div>
  )
}

const StatCard = ({ label, value }: { label: string, value: string | number }) => (
  <div className="rounded-lg border border-divider-subtle bg-background-default px-3 py-2">
    <div className="text-xs text-text-tertiary">{label}</div>
    <div className="mt-1 text-base font-semibold text-text-primary">{value}</div>
  </div>
)

const FilterCheckbox = ({
  checked,
  label,
  count,
  onChange,
}: {
  checked: boolean
  label: string
  count?: number
  onChange: () => void
}) => (
  <button
    type="button"
    className={`flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left text-sm hover:bg-state-base-hover ${checked ? 'text-text-primary' : 'text-text-secondary'}`}
    onClick={onChange}
  >
    <span className={`flex size-4 shrink-0 items-center justify-center rounded border text-[10px] leading-none ${checked ? 'border-components-button-primary-bg bg-components-button-primary-bg text-text-primary-on-surface' : 'border-divider-regular bg-background-default'}`}>
      {checked ? '✓' : ''}
    </span>
    <span className="min-w-0 flex-1 truncate" title={label}>{label}</span>
    {typeof count === 'number' && <span className="shrink-0 text-xs text-text-tertiary tabular-nums">{count}</span>}
  </button>
)

const FilterSection = ({
  title,
  icon,
  items,
  selectedIds,
  onToggle,
  onSelectAll,
}: {
  title: string
  icon: ReactNode
  items: GeneratedAssetFacet[]
  selectedIds: string[]
  onToggle: (id: string) => void
  onSelectAll: () => void
}) => {
  const total = items.reduce((sum, item) => sum + item.count, 0)

  return (
    <section className="space-y-1.5">
      <div className="flex items-center gap-1.5 px-2 text-xs font-medium text-text-tertiary">
        {icon}
        <span>{title}</span>
      </div>
      <FilterCheckbox checked={selectedIds.length === 0} label="全量" count={total} onChange={onSelectAll} />
      <div className="max-h-[220px] space-y-1 overflow-auto pr-1">
        {items.map(item => (
          <FilterCheckbox
            key={item.id}
            checked={selectedIds.includes(item.id)}
            label={item.name}
            count={item.count}
            onChange={() => onToggle(item.id)}
          />
        ))}
      </div>
    </section>
  )
}

const GeneratedAssetsLibrary = () => {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const debouncedKeyword = useDebounce(keyword.trim(), { wait: 400 })
  const [page, setPage] = useState(1)
  const [fileType, setFileType] = useState('all')
  const [sourceKind, setSourceKind] = useState('all')
  const [createdAfter, setCreatedAfter] = useState('')
  const [createdBefore, setCreatedBefore] = useState('')
  const [selectedOwnerIds, setSelectedOwnerIds] = useState<string[]>([])
  const [selectedAppIds, setSelectedAppIds] = useState<string[]>([])
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const queryParams = useMemo(() => ({
    page,
    limit: PAGE_SIZE,
    keyword: debouncedKeyword || undefined,
    file_type: fileType === 'all' ? undefined : fileType,
    owner_user_ids: selectedOwnerIds.length ? selectedOwnerIds.join(',') : undefined,
    source_app_ids: selectedAppIds.length ? selectedAppIds.join(',') : undefined,
    source_kind: sourceKind === 'all' ? undefined : sourceKind,
    created_after: dateToTimestamp(createdAfter),
    created_before: dateToTimestamp(createdBefore, true),
    include_all: true,
    sort: '-created_at',
  }), [createdAfter, createdBefore, debouncedKeyword, fileType, page, selectedAppIds, selectedOwnerIds, sourceKind])

  const { data, isLoading, isFetching, isError, refetch } = useQuery({
    queryKey: ['document-management', 'generated-assets', queryParams],
    queryFn: () => fetchGeneratedAssets(queryParams),
    staleTime: 30 * 1000,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteGeneratedAsset,
    onSuccess: () => {
      toast.success('已从生成内容中移除')
      queryClient.invalidateQueries({ queryKey: ['document-management', 'generated-assets'] })
    },
    onError: () => toast.error('移除失败'),
  })

  const handleDownload = async (file: GeneratedAsset) => {
    if (downloadingId)
      return
    setDownloadingId(file.id)
    const [error, response] = await asyncRunSafe(fetchGeneratedAssetDownloadUrl(file.id))
    setDownloadingId(null)
    if (error || !response?.url) {
      toast.error('下载链接生成失败')
      return
    }
    if (file.storage_type === 'remote_url') {
      window.open(response.url, '_blank', 'noopener,noreferrer')
      return
    }
    downloadUrl({ url: response.url, fileName: file.name })
  }

  const handlePreview = (file: GeneratedAsset) => {
    if (!isPreviewable(file))
      return
    const params = new URLSearchParams({ generatedAssetId: file.id })
    window.open(`/document-management/preview?${params.toString()}`, '_blank', 'noopener,noreferrer')
  }

  const handleRemove = (file: GeneratedAsset) => {
    if (!window.confirm('只会从资产索引移除，不会删除聊天记录或源文件。继续吗？'))
      return
    deleteMutation.mutate(file.id)
  }

  const toggleSelected = (id: string, selectedIds: string[], setSelectedIds: (ids: string[]) => void) => {
    setPage(1)
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter(item => item !== id))
      return
    }
    setSelectedIds([...selectedIds, id])
  }

  const files = data?.data ?? []
  const stats = data?.stats
  const accountFacets = data?.facets?.accounts ?? []
  const appFacets = data?.facets?.apps ?? []
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / (data?.limit || PAGE_SIZE)))

  useEffect(() => {
    if (data && page > totalPages)
      setPage(totalPages)
  }, [data, page, totalPages])

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard label="生成内容" value={stats?.total ?? 0} />
        <StatCard label="图片" value={stats?.by_type?.image ?? 0} />
        <StatCard label="视频" value={stats?.by_type?.video ?? 0} />
        <StatCard label="文档/PPT/表格" value={(stats?.by_type?.document ?? 0) + (stats?.by_type?.presentation ?? 0) + (stats?.by_type?.spreadsheet ?? 0)} />
        <StatCard label="占用空间" value={formatSize(stats?.total_size)} />
      </div>

      <div className="flex min-h-0 flex-1 gap-3">
        <aside className="hidden w-[260px] shrink-0 flex-col gap-4 overflow-auto rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-3 shadow-xs md:flex">
          <FilterSection
            title="使用者"
            icon={<RiUser3Line className="size-3.5" />}
            items={accountFacets}
            selectedIds={selectedOwnerIds}
            onToggle={id => toggleSelected(id, selectedOwnerIds, setSelectedOwnerIds)}
            onSelectAll={() => {
              setPage(1)
              setSelectedOwnerIds([])
            }}
          />
          <div className="h-px shrink-0 bg-divider-subtle" />
          <FilterSection
            title="应用"
            icon={<RiApps2Line className="size-3.5" />}
            items={appFacets}
            selectedIds={selectedAppIds}
            onToggle={id => toggleSelected(id, selectedAppIds, setSelectedAppIds)}
            onSelectAll={() => {
              setPage(1)
              setSelectedAppIds([])
            }}
          />
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg shadow-xs">
          <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-divider-subtle bg-background-default px-3 py-2.5">
            <div className="relative min-w-[240px] flex-1">
              <RiSearchLine className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-quaternary" />
              <input
                aria-label="搜索生成内容"
                value={keyword}
                onChange={(event) => {
                  setPage(1)
                  setKeyword(event.target.value)
                }}
                placeholder="搜索内容名称"
                className="h-8 w-full rounded-lg border border-transparent bg-components-input-bg-normal pr-3 pl-8 text-sm text-text-primary outline-none placeholder:text-text-quaternary hover:border-components-input-border-hover focus:border-components-input-border-active"
              />
            </div>
            <select
              aria-label="内容类型"
              value={fileType}
              onChange={(event) => {
                setPage(1)
                setFileType(event.target.value)
              }}
              className="border-components-input-border h-8 rounded-lg border bg-components-input-bg-normal px-2.5 text-sm text-text-secondary outline-none"
            >
              {fileTypeOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <select
              aria-label="内容来源"
              value={sourceKind}
              onChange={(event) => {
                setPage(1)
                setSourceKind(event.target.value)
              }}
              className="border-components-input-border h-8 rounded-lg border bg-components-input-bg-normal px-2.5 text-sm text-text-secondary outline-none"
            >
              {sourceKindOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <select
              aria-label="使用者"
              value={selectedOwnerIds[0] || ''}
              onChange={(event) => {
                setPage(1)
                setSelectedOwnerIds(event.target.value ? [event.target.value] : [])
              }}
              className="border-components-input-border h-8 max-w-[160px] rounded-lg border bg-components-input-bg-normal px-2 text-sm text-text-secondary outline-none md:hidden"
            >
              <option value="">全部使用者</option>
              {accountFacets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
            <select
              aria-label="应用"
              value={selectedAppIds[0] || ''}
              onChange={(event) => {
                setPage(1)
                setSelectedAppIds(event.target.value ? [event.target.value] : [])
              }}
              className="border-components-input-border h-8 max-w-[160px] rounded-lg border bg-components-input-bg-normal px-2 text-sm text-text-secondary outline-none md:hidden"
            >
              <option value="">全部应用</option>
              {appFacets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
            <input
              aria-label="开始日期"
              type="date"
              value={createdAfter}
              max={createdBefore || undefined}
              onChange={(event) => {
                setPage(1)
                setCreatedAfter(event.target.value)
              }}
              className="border-components-input-border h-8 rounded-lg border bg-components-input-bg-normal px-2 text-xs text-text-secondary outline-none"
            />
            <input
              aria-label="结束日期"
              type="date"
              value={createdBefore}
              min={createdAfter || undefined}
              onChange={(event) => {
                setPage(1)
                setCreatedBefore(event.target.value)
              }}
              className="border-components-input-border h-8 rounded-lg border bg-components-input-bg-normal px-2 text-xs text-text-secondary outline-none"
            />
            <button
              type="button"
              disabled={isFetching}
              className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-xs font-medium text-components-button-secondary-text shadow-xs hover:bg-components-button-secondary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() => refetch()}
            >
              <RiRefreshLine className={`size-3.5 ${isFetching ? 'animate-spin' : ''}`} />
              刷新
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-auto">
            {isLoading
              ? (
                  <div className="flex h-full items-center justify-center text-sm text-text-tertiary">加载中...</div>
                )
              : isError
                ? (
                    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
                      <div className="text-sm font-medium text-text-secondary">生成内容加载失败</div>
                      <button
                        type="button"
                        disabled={isFetching}
                        className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-xs font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={() => refetch()}
                      >
                        <RiRefreshLine className={`size-3.5 ${isFetching ? 'animate-spin' : ''}`} />
                        重试
                      </button>
                    </div>
                  )
              : files.length === 0
                ? (
                    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                      <div className="flex size-10 items-center justify-center rounded-lg bg-background-section text-text-quaternary">
                        <RiFileList3Line className="size-5" />
                      </div>
                      <div className="mt-3 text-sm font-medium text-text-secondary">暂无生成内容</div>
                    </div>
                  )
                : (
                    <table className="w-full min-w-[1220px] table-fixed border-collapse text-sm">
                      <thead className="sticky top-0 z-10 border-b border-divider-subtle bg-background-default-subtle text-xs font-medium text-text-tertiary">
                        <tr>
                          <th className="w-[340px] px-3 py-2.5 text-left">内容</th>
                          <th className="w-[100px] px-3 py-2.5 text-left">类型</th>
                          <th className="w-[160px] px-3 py-2.5 text-left">使用者</th>
                          <th className="w-[210px] px-3 py-2.5 text-left">来源</th>
                          <th className="w-[100px] px-3 py-2.5 text-right">大小</th>
                          <th className="w-[150px] px-3 py-2.5 text-left">生成时间</th>
                          <th className="w-[180px] px-3 py-2.5 text-left">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {files.map(file => (
                          <tr key={file.id} className="group border-b border-divider-subtle last:border-b-0 hover:bg-state-base-hover">
                            <td className="px-3 py-2.5 align-middle">
                              <div className="flex min-w-0 items-center gap-2">
                                <GeneratedAssetIcon asset={file} />
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-medium text-text-primary" title={file.name}>{file.name}</div>
                                  <div className="mt-0.5 text-xs text-text-tertiary">{file.extension ? `.${file.extension}` : file.mime_type || '-'}</div>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-2.5 align-middle text-text-secondary">{fileTypeLabel[file.file_type] || file.file_type}</td>
                            <td className="px-3 py-2.5 align-middle text-text-secondary">
                              <span className="block truncate" title={file.owner_name || '未知使用者'}>{file.owner_name || '未知使用者'}</span>
                            </td>
                            <td className="px-3 py-2.5 align-middle text-text-secondary">
                              <span className="block truncate" title={file.source_app_name || sourceKindLabel[file.source_kind || ''] || '未知来源'}>{file.source_app_name || sourceKindLabel[file.source_kind || ''] || '未知来源'}</span>
                              {file.source_app_name && file.source_kind && <span className="mt-0.5 block truncate text-xs text-text-tertiary">{sourceKindLabel[file.source_kind] || file.source_kind}</span>}
                            </td>
                            <td className="px-3 py-2.5 text-right align-middle text-text-secondary tabular-nums">{formatSize(file.size)}</td>
                            <td className="px-3 py-2.5 align-middle text-text-tertiary">{formatTime(file.created_at)}</td>
                            <td className="px-3 py-2.5 align-middle whitespace-nowrap">
                              <div className="flex items-center gap-1.5 whitespace-nowrap">
                                <button
                                  type="button"
                                  disabled={!isPreviewable(file)}
                                  className="inline-flex h-7 shrink-0 items-center rounded-lg px-2 text-xs font-medium text-text-secondary hover:bg-state-base-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                                  onClick={() => handlePreview(file)}
                                >
                                  预览
                                </button>
                                <button
                                  type="button"
                                  disabled={downloadingId === file.id}
                                  className="inline-flex h-7 shrink-0 items-center gap-1 rounded-lg px-2 text-xs font-medium text-text-secondary hover:bg-state-base-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                                  onClick={() => handleDownload(file)}
                                >
                                  <RiDownload2Line className="size-3.5" />
                                  {downloadingId === file.id ? '准备中' : file.storage_type === 'remote_url' ? '打开' : '下载'}
                                </button>
                                <button
                                  type="button"
                                  disabled={deleteMutation.isPending}
                                  className="inline-flex h-7 shrink-0 items-center rounded-lg px-2 text-xs font-medium text-text-tertiary hover:bg-state-destructive-hover hover:text-text-destructive disabled:cursor-not-allowed disabled:opacity-40"
                                  onClick={() => handleRemove(file)}
                                >
                                  移除
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
          </div>
          <div className="flex h-11 shrink-0 items-center justify-end gap-2 border-t border-divider-subtle bg-background-default px-3 text-xs text-text-tertiary">
            <span>第 {page} / {totalPages} 页 · 共 {data?.total ?? 0} 条</span>
            <button
              type="button"
              aria-label="上一页"
              title="上一页"
              disabled={page <= 1 || isFetching}
              className="flex size-7 items-center justify-center rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover disabled:cursor-not-allowed disabled:opacity-40"
              onClick={() => setPage(current => Math.max(1, current - 1))}
            >
              <RiArrowLeftSLine className="size-4" />
            </button>
            <button
              type="button"
              aria-label="下一页"
              title="下一页"
              disabled={page >= totalPages || isFetching}
              className="flex size-7 items-center justify-center rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover disabled:cursor-not-allowed disabled:opacity-40"
              onClick={() => setPage(current => Math.min(totalPages, current + 1))}
            >
              <RiArrowRightSLine className="size-4" />
            </button>
          </div>
        </main>
      </div>
    </div>
  )
}

export default GeneratedAssetsLibrary
