'use client'

import type { DataSet, SimpleDocumentDetail } from '@/models/datasets'
import { toast } from '@langgenius/dify-ui/toast'
import {
  RiDatabase2Line,
  RiDownload2Line,
  RiFileList3Line,
  RiFolderOpenLine,
  RiRefreshLine,
  RiSearchLine,
} from '@remixicon/react'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import Loading from '@/app/components/base/loading'
import useDocumentTitle from '@/hooks/use-document-title'
import { DataSourceType } from '@/models/datasets'
import Link from '@/next/link'
import { fetchDatasets, fetchDocumentDownloadUrl, fetchDocuments } from '@/service/datasets'
import { asyncRunSafe } from '@/utils'
import { downloadUrl } from '@/utils/download'

type ManagedDocument = SimpleDocumentDetail & {
  dataset: Pick<DataSet, 'id' | 'name' | 'provider' | 'runtime_mode'>
}

type DocumentManagementData = {
  datasets: DataSet[]
  documents: ManagedDocument[]
}

const formatTime = (timestamp?: number) => {
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

const statusLabel: Record<string, string> = {
  available: '可用',
  enabled: '已启用',
  disabled: '已停用',
  archived: '已归档',
  indexing: '索引中',
  queuing: '排队中',
  paused: '已暂停',
  error: '异常',
  completed: '完成',
}

const statusClassName = (status: string) => {
  if (['available', 'enabled', 'completed'].includes(status))
    return 'bg-state-success-bg text-text-success'
  if (['indexing', 'queuing', 'paused'].includes(status))
    return 'bg-state-warning-bg text-text-warning'
  if (status === 'error')
    return 'bg-state-destructive-bg text-text-destructive'
  return 'bg-background-section text-text-tertiary'
}

const isDownloadable = (doc: ManagedDocument) => {
  if (![DataSourceType.FILE, DataSourceType.LOCAL_FILE].includes(doc.data_source_type as DataSourceType))
    return false

  const sourceInfo = doc.data_source_info
  return !!sourceInfo && typeof sourceInfo === 'object'
    && ('upload_file_id' in sourceInfo || 'related_id' in sourceInfo)
}

const fetchAllDatasets = async () => {
  const datasets: DataSet[] = []
  let page = 1
  let hasMore = true

  while (hasMore) {
    const response = await fetchDatasets({
      url: '/datasets',
      params: {
        page,
        limit: 100,
        include_all: true,
      },
    })
    datasets.push(...response.data)
    hasMore = response.has_more
    page += 1
  }

  return datasets
}

const fetchDatasetDocuments = async (dataset: DataSet) => {
  const documents: ManagedDocument[] = []
  let page = 1
  let hasMore = true

  while (hasMore) {
    const response = await fetchDocuments({
      datasetId: dataset.id,
      query: {
        page,
        limit: 100,
        keyword: '',
        sort: '-created_at',
      },
    })
    documents.push(...response.data.map((document: SimpleDocumentDetail) => ({
      ...document,
      dataset: {
        id: dataset.id,
        name: dataset.name,
        provider: dataset.provider,
        runtime_mode: dataset.runtime_mode,
      },
    })))
    hasMore = response.has_more
    page += 1
  }

  return documents
}

const fetchDocumentManagementData = async (): Promise<DocumentManagementData> => {
  const datasets = await fetchAllDatasets()
  const localDatasets = datasets.filter(dataset => dataset.provider !== 'external')
  const documentGroups = await Promise.all(localDatasets.map(fetchDatasetDocuments))
  const documents = documentGroups.flat().sort((a, b) => b.created_at - a.created_at)

  return {
    datasets: localDatasets,
    documents,
  }
}

const DocumentManagement = () => {
  useDocumentTitle('文档管理')
  const [keyword, setKeyword] = useState('')
  const [datasetId, setDatasetId] = useState('all')
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['document-management', 'documents'],
    queryFn: fetchDocumentManagementData,
    staleTime: 30 * 1000,
  })

  const filteredDocuments = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase()
    return (data?.documents ?? []).filter((doc) => {
      const matchDataset = datasetId === 'all' || doc.dataset.id === datasetId
      const matchKeyword = !normalizedKeyword
        || doc.name.toLowerCase().includes(normalizedKeyword)
        || doc.dataset.name.toLowerCase().includes(normalizedKeyword)
      return matchDataset && matchKeyword
    })
  }, [data?.documents, datasetId, keyword])

  const selectedDatasetName = datasetId === 'all'
    ? '全部知识库'
    : data?.datasets.find(dataset => dataset.id === datasetId)?.name || '当前知识库'

  const handleDownload = async (doc: ManagedDocument) => {
    if (!isDownloadable(doc) || downloadingId)
      return

    setDownloadingId(doc.id)
    const [error, response] = await asyncRunSafe(fetchDocumentDownloadUrl({
      datasetId: doc.dataset.id,
      documentId: doc.id,
    }))
    setDownloadingId(null)

    if (error || !response?.url) {
      toast.error('下载链接生成失败')
      return
    }

    downloadUrl({ url: response.url, fileName: doc.name })
  }

  const handlePreview = (doc: ManagedDocument) => {
    if (!isDownloadable(doc))
      return

    const params = new URLSearchParams({
      datasetId: doc.dataset.id,
      documentId: doc.id,
    })
    window.open(`/document-management/preview?${params.toString()}`, '_blank', 'noopener,noreferrer')
  }

  const totalDocuments = data?.documents.length ?? 0
  const downloadableDocuments = data?.documents.filter(isDownloadable).length ?? 0
  const availableDocuments = data?.documents.filter(doc => ['available', 'enabled', 'completed'].includes(doc.display_status || doc.indexing_status)).length ?? 0

  if (isLoading && !data)
    return <Loading type="app" />

  return (
    <div className="flex h-full flex-col bg-background-default-subtle">
      <div className="shrink-0 border-b border-divider-subtle bg-background-default px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-xs font-medium text-text-tertiary">
              <RiFolderOpenLine className="size-3.5" />
              <span>知识库</span>
              <span>/</span>
              <span className="text-text-secondary">文档管理</span>
            </div>
            <div className="mt-1 flex items-center gap-3">
              <h1 className="text-xl font-semibold text-text-primary">文档管理</h1>
              <div className="hidden items-center gap-2 text-xs text-text-tertiary sm:flex">
                <span>
                  {data?.datasets.length ?? 0}
                  {' '}
                  个知识库
                </span>
                <span className="size-1 rounded-full bg-divider-regular" />
                <span>
                  {totalDocuments}
                  {' '}
                  份文档
                </span>
                <span className="size-1 rounded-full bg-divider-regular" />
                <span>
                  {downloadableDocuments}
                  {' '}
                  份可下载
                </span>
              </div>
            </div>
          </div>
          <button
            type="button"
            className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-xs font-medium text-components-button-secondary-text shadow-xs hover:bg-components-button-secondary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isFetching}
            onClick={() => refetch()}
          >
            <RiRefreshLine className={`size-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-3 p-4">
        <aside className="hidden w-[264px] shrink-0 flex-col overflow-hidden rounded-xl border-[0.5px] border-components-panel-border bg-components-panel-bg shadow-xs md:flex">
          <div className="border-b border-divider-subtle px-3 py-3">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold text-text-primary">知识库</div>
              <span className="rounded-md bg-background-section px-1.5 py-0.5 text-xs text-text-tertiary">{data?.datasets.length ?? 0}</span>
            </div>
            <div className="mt-1 truncate text-xs text-text-tertiary" title={selectedDatasetName}>{selectedDatasetName}</div>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
            <button
              type="button"
              className={`flex h-8 w-full items-center justify-between rounded-lg px-2.5 text-left text-sm ${datasetId === 'all' ? 'bg-state-accent-hover text-text-accent' : 'text-text-secondary hover:bg-state-base-hover'}`}
              onClick={() => setDatasetId('all')}
            >
              <span className="truncate">全部知识库</span>
              <span className="ml-2 rounded-md bg-background-section px-1.5 py-0.5 text-xs text-text-tertiary">{totalDocuments}</span>
            </button>
            {(data?.datasets ?? []).map(dataset => (
              <button
                key={dataset.id}
                type="button"
                className={`mt-0.5 flex h-8 w-full items-center justify-between rounded-lg px-2.5 text-left text-sm ${datasetId === dataset.id ? 'bg-state-accent-hover text-text-accent' : 'text-text-secondary hover:bg-state-base-hover'}`}
                onClick={() => setDatasetId(dataset.id)}
              >
                <span className="truncate" title={dataset.name}>{dataset.name}</span>
                <span className="ml-2 rounded-md bg-background-section px-1.5 py-0.5 text-xs text-text-tertiary">{dataset.document_count}</span>
              </button>
            ))}
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border-[0.5px] border-components-panel-border bg-components-panel-bg shadow-xs">
          <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-divider-subtle bg-background-default px-3 py-2.5">
            <div className="relative min-w-[240px] flex-1">
              <RiSearchLine className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-quaternary" />
              <input
                value={keyword}
                onChange={event => setKeyword(event.target.value)}
                placeholder="搜索文档名或知识库"
                className="h-8 w-full rounded-lg border border-transparent bg-components-input-bg-normal pr-3 pl-8 text-sm text-text-primary outline-none placeholder:text-text-quaternary hover:border-components-input-border-hover focus:border-components-input-border-active"
              />
            </div>
            <select
              value={datasetId}
              onChange={event => setDatasetId(event.target.value)}
              className="border-components-input-border h-8 max-w-[220px] rounded-lg border bg-components-input-bg-normal px-2.5 text-sm text-text-secondary outline-none md:hidden"
            >
              <option value="all">全部知识库</option>
              {(data?.datasets ?? []).map(dataset => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}
            </select>
            <div className="flex h-8 items-center rounded-lg bg-background-section px-2.5 text-xs font-medium text-text-tertiary">
              {filteredDocuments.length}
              <span className="mx-1 text-text-quaternary">/</span>
              {totalDocuments}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-auto">
            {filteredDocuments.length === 0
              ? (
                  <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                    <div className="flex size-10 items-center justify-center rounded-xl bg-background-section text-text-quaternary">
                      <RiFileList3Line className="size-5" />
                    </div>
                    <div className="mt-3 text-sm font-medium text-text-secondary">没有匹配的文档</div>
                    <div className="mt-1 text-xs text-text-tertiary">换一个关键词或选择全部知识库。</div>
                  </div>
                )
              : (
                  <table className="w-full min-w-[1120px] border-collapse text-sm">
                    <thead className="sticky top-0 z-10 border-b border-divider-subtle bg-background-default-subtle text-xs font-medium text-text-tertiary">
                      <tr>
                        <th className="w-[34%] px-3 py-2.5 text-left">文档</th>
                        <th className="w-[24%] px-3 py-2.5 text-left">知识库</th>
                        <th className="w-[9%] px-3 py-2.5 text-right">字符数</th>
                        <th className="w-[7%] px-3 py-2.5 text-right">召回</th>
                        <th className="w-[8%] px-3 py-2.5 text-left">状态</th>
                        <th className="w-[220px] min-w-[220px] px-3 py-2.5 text-left">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDocuments.map((doc) => {
                        const status = doc.display_status || doc.indexing_status
                        return (
                          <tr key={`${doc.dataset.id}-${doc.id}`} className="group border-b border-divider-subtle last:border-b-0 hover:bg-state-base-hover">
                            <td className="px-3 py-2.5 align-middle">
                              <div className="flex min-w-0 items-center gap-2">
                                <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-background-section text-text-tertiary">
                                  <RiFileList3Line className="size-4" />
                                </div>
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-medium text-text-primary" title={doc.name}>{doc.name}</div>
                                  <div className="mt-0.5 text-xs text-text-tertiary">{formatTime(doc.created_at)}</div>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-2.5 align-middle">
                              <div className="flex min-w-0 items-center gap-1.5 text-text-secondary">
                                <RiDatabase2Line className="size-3.5 shrink-0 text-text-quaternary" />
                                <span className="truncate" title={doc.dataset.name}>{doc.dataset.name}</span>
                              </div>
                            </td>
                            <td className="px-3 py-2.5 text-right align-middle text-text-secondary tabular-nums">{doc.word_count?.toLocaleString() || 0}</td>
                            <td className="px-3 py-2.5 text-right align-middle text-text-secondary tabular-nums">{doc.hit_count?.toLocaleString() || 0}</td>
                            <td className="px-3 py-2.5 align-middle">
                              <span className={`inline-flex h-6 items-center gap-1.5 rounded-md px-2 text-xs font-medium ${statusClassName(status)}`}>
                                <span className="size-1.5 rounded-full bg-current opacity-70" />
                                {statusLabel[status] || status}
                              </span>
                            </td>
                            <td className="w-[220px] min-w-[220px] px-3 py-2.5 align-middle">
                              <div className="flex items-center gap-1.5 whitespace-nowrap">
                                <Link
                                  href={`/datasets/${doc.dataset.id}/documents/${doc.id}`}
                                  className="inline-flex h-7 shrink-0 items-center rounded-lg px-2 text-xs font-medium text-text-secondary hover:bg-state-base-hover hover:text-text-primary"
                                >
                                  分段
                                </Link>
                                <button
                                  type="button"
                                  disabled={!isDownloadable(doc)}
                                  className="inline-flex h-7 shrink-0 items-center rounded-lg px-2 text-xs font-medium text-text-secondary hover:bg-state-base-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                                  onClick={() => handlePreview(doc)}
                                >
                                  预览
                                </button>
                                <button
                                  type="button"
                                  disabled={!isDownloadable(doc) || downloadingId === doc.id}
                                  className="inline-flex h-7 shrink-0 items-center gap-1 rounded-lg px-2 text-xs font-medium text-text-secondary hover:bg-state-base-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                                  onClick={() => handleDownload(doc)}
                                >
                                  <RiDownload2Line className="size-3.5" />
                                  {downloadingId === doc.id ? '准备中' : '下载'}
                                </button>
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
          </div>

          <div className="flex h-10 shrink-0 items-center justify-between gap-3 border-t border-divider-subtle bg-background-default px-3 text-xs text-text-tertiary">
            <span>
              {availableDocuments}
              {' '}
              份可用
            </span>
            <span className="hidden min-w-0 truncate sm:inline" title={selectedDatasetName}>{selectedDatasetName}</span>
          </div>
        </main>
      </div>
    </div>
  )
}

export default DocumentManagement
