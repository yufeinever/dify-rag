'use client'

import type { GeneratedFile, GeneratedFileFacet } from '@/service/generated-files'
import { toast } from '@langgenius/dify-ui/toast'
import {
  RiApps2Line,
  RiDownload2Line,
  RiFileList3Line,
  RiRefreshLine,
  RiSearchLine,
  RiUser3Line,
} from '@remixicon/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useMemo, useState } from 'react'
import { deleteGeneratedFile, fetchGeneratedFileDownloadUrl, fetchGeneratedFiles } from '@/service/generated-files'
import { asyncRunSafe } from '@/utils'
import { downloadUrl } from '@/utils/download'

const fileTypeOptions = [
  { value: 'all', label: '全部类型' },
  { value: 'image', label: '图片' },
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

const isPreviewable = (file: GeneratedFile) => file.preview_kind !== 'unsupported'

const GeneratedFileIcon = ({ file }: { file: GeneratedFile }) => {
  if (file.file_type === 'image' && file.preview_url) {
    return (
      <div className="flex size-10 shrink-0 overflow-hidden rounded-lg border border-divider-subtle bg-background-section">
        <img src={file.preview_url} alt={file.name} className="h-full w-full object-cover" />
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
  items: GeneratedFileFacet[]
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

const GeneratedFilesLibrary = () => {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [fileType, setFileType] = useState('all')
  const [selectedOwnerIds, setSelectedOwnerIds] = useState<string[]>([])
  const [selectedAppIds, setSelectedAppIds] = useState<string[]>([])
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const queryParams = useMemo(() => ({
    page: 1,
    limit: 100,
    keyword: keyword.trim() || undefined,
    file_type: fileType,
    owner_user_ids: selectedOwnerIds.length ? selectedOwnerIds.join(',') : undefined,
    source_app_ids: selectedAppIds.length ? selectedAppIds.join(',') : undefined,
    include_all: true,
    sort: '-created_at',
  }), [fileType, keyword, selectedAppIds, selectedOwnerIds])

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['document-management', 'generated-files', queryParams],
    queryFn: () => fetchGeneratedFiles(queryParams),
    staleTime: 30 * 1000,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteGeneratedFile,
    onSuccess: () => {
      toast.success('已从生成文件库移除')
      queryClient.invalidateQueries({ queryKey: ['document-management', 'generated-files'] })
    },
    onError: () => toast.error('移除失败'),
  })

  const handleDownload = async (file: GeneratedFile) => {
    if (downloadingId)
      return
    setDownloadingId(file.id)
    const [error, response] = await asyncRunSafe(fetchGeneratedFileDownloadUrl(file.id))
    setDownloadingId(null)
    if (error || !response?.url) {
      toast.error('下载链接生成失败')
      return
    }
    downloadUrl({ url: response.url, fileName: file.name })
  }

  const handlePreview = (file: GeneratedFile) => {
    if (!isPreviewable(file))
      return
    const params = new URLSearchParams({ generatedFileId: file.id })
    window.open(`/document-management/preview?${params.toString()}`, '_blank', 'noopener,noreferrer')
  }

  const handleRemove = (file: GeneratedFile) => {
    if (!window.confirm('只会从生成文件库移除，不会删除聊天记录或知识库材料。继续吗？'))
      return
    deleteMutation.mutate(file.id)
  }

  const toggleSelected = (id: string, selectedIds: string[], setSelectedIds: (ids: string[]) => void) => {
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

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="生成文件" value={stats?.total ?? 0} />
        <StatCard label="图片" value={stats?.by_type?.image ?? 0} />
        <StatCard label="文档/PPT/表格" value={(stats?.by_type?.document ?? 0) + (stats?.by_type?.presentation ?? 0) + (stats?.by_type?.spreadsheet ?? 0)} />
        <StatCard label="占用空间" value={formatSize(stats?.total_size)} />
      </div>

      <div className="flex min-h-0 flex-1 gap-3">
        <aside className="flex w-[260px] shrink-0 flex-col gap-4 overflow-hidden rounded-xl border-[0.5px] border-components-panel-border bg-components-panel-bg p-3 shadow-xs">
          <FilterSection
            title="账户"
            icon={<RiUser3Line className="size-3.5" />}
            items={accountFacets}
            selectedIds={selectedOwnerIds}
            onToggle={id => toggleSelected(id, selectedOwnerIds, setSelectedOwnerIds)}
            onSelectAll={() => setSelectedOwnerIds([])}
          />
          <div className="h-px shrink-0 bg-divider-subtle" />
          <FilterSection
            title="应用"
            icon={<RiApps2Line className="size-3.5" />}
            items={appFacets}
            selectedIds={selectedAppIds}
            onToggle={id => toggleSelected(id, selectedAppIds, setSelectedAppIds)}
            onSelectAll={() => setSelectedAppIds([])}
          />
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border-[0.5px] border-components-panel-border bg-components-panel-bg shadow-xs">
          <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-divider-subtle bg-background-default px-3 py-2.5">
            <div className="relative min-w-[240px] flex-1">
              <RiSearchLine className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-quaternary" />
              <input
                value={keyword}
                onChange={event => setKeyword(event.target.value)}
                placeholder="搜索文件名"
                className="h-8 w-full rounded-lg border border-transparent bg-components-input-bg-normal pr-3 pl-8 text-sm text-text-primary outline-none placeholder:text-text-quaternary hover:border-components-input-border-hover focus:border-components-input-border-active"
              />
            </div>
            <select
              value={fileType}
              onChange={event => setFileType(event.target.value)}
              className="border-components-input-border h-8 rounded-lg border bg-components-input-bg-normal px-2.5 text-sm text-text-secondary outline-none"
            >
              {fileTypeOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
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
              : files.length === 0
                ? (
                    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                      <div className="flex size-10 items-center justify-center rounded-xl bg-background-section text-text-quaternary">
                        <RiFileList3Line className="size-5" />
                      </div>
                      <div className="mt-3 text-sm font-medium text-text-secondary">暂无生成文件</div>
                      <div className="mt-1 text-xs text-text-tertiary">通过 Agent 生成的 Word、PPT、Excel 或图片会出现在这里。</div>
                    </div>
                  )
                : (
                    <table className="w-full min-w-[1040px] table-fixed border-collapse text-sm">
                      <thead className="sticky top-0 z-10 border-b border-divider-subtle bg-background-default-subtle text-xs font-medium text-text-tertiary">
                        <tr>
                          <th className="w-[420px] px-3 py-2.5 text-left">文件</th>
                          <th className="w-[110px] px-3 py-2.5 text-left">类型</th>
                          <th className="w-[220px] px-3 py-2.5 text-left">来源</th>
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
                                <GeneratedFileIcon file={file} />
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-medium text-text-primary" title={file.name}>{file.name}</div>
                                  <div className="mt-0.5 text-xs text-text-tertiary">.{file.extension || 'bin'}</div>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-2.5 align-middle text-text-secondary">{fileTypeLabel[file.file_type] || file.file_type}</td>
                            <td className="px-3 py-2.5 align-middle text-text-secondary">
                              <span className="truncate" title={file.source_app_name || '未知来源'}>{file.source_app_name || '未知来源'}</span>
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
                                  {downloadingId === file.id ? '准备中' : '下载'}
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
        </main>
      </div>
    </div>
  )
}

export default GeneratedFilesLibrary
