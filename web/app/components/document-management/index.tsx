'use client'

import type { DataSet, SimpleDocumentDetail } from '@/models/datasets'
import { toast } from '@langgenius/dify-ui/toast'
import {
  RiArrowRightLine,
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
import { fetchDatasets, fetchDocumentDownloadUrl, fetchDocumentPreviewUrl, fetchDocuments } from '@/service/datasets'
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
  if (doc.data_source_type !== DataSourceType.FILE)
    return false

  const sourceInfo = doc.data_source_info
  return !!sourceInfo && typeof sourceInfo === 'object' && 'upload_file_id' in sourceInfo
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
  const [previewingId, setPreviewingId] = useState<string | null>(null)

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

  const handlePreview = async (doc: ManagedDocument) => {
    if (!isDownloadable(doc) || previewingId)
      return

    setPreviewingId(doc.id)
    const [error, response] = await asyncRunSafe(fetchDocumentPreviewUrl({
      datasetId: doc.dataset.id,
      documentId: doc.id,
    }))
    setPreviewingId(null)

    if (error || !response?.url) {
      toast.error('原文预览链接生成失败')
      return
    }

    window.open(response.url, '_blank', 'noopener,noreferrer')
  }

  const totalDocuments = data?.documents.length ?? 0
  const downloadableDocuments = data?.documents.filter(isDownloadable).length ?? 0
  const availableDocuments = data?.documents.filter(doc => ['available', 'enabled', 'completed'].includes(doc.display_status || doc.indexing_status)).length ?? 0

  if (isLoading && !data)
    return <Loading type="app" />

  return (
    <div className="flex h-full flex-col bg-background-body">
      <div className="border-b border-divider-subtle px-8 py-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-text-tertiary">
              <RiFolderOpenLine className="size-4" />
              知识库文档中心
            </div>
            <h1 className="mt-2 text-2xl font-semibold text-text-primary">文档管理</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-text-tertiary">
              统一管理知识库中的入库文档，集中查看索引状态、来源知识库、召回次数，并下载 Dify 保存的原始上传文件。
            </p>
          </div>
          <button
            type="button"
            className="inline-flex h-9 items-center gap-2 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-sm font-medium text-components-button-secondary-text shadow-xs hover:bg-components-button-secondary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isFetching}
            onClick={() => refetch()}
          >
            <RiRefreshLine className="size-4" />
            刷新
          </button>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-divider-subtle bg-background-default px-4 py-3">
            <div className="text-xs text-text-tertiary">知识库</div>
            <div className="mt-1 flex items-end gap-2">
              <span className="text-2xl font-semibold text-text-primary">{data?.datasets.length ?? 0}</span>
              <span className="pb-1 text-xs text-text-tertiary">个可管理知识库</span>
            </div>
          </div>
          <div className="rounded-lg border border-divider-subtle bg-background-default px-4 py-3">
            <div className="text-xs text-text-tertiary">文档</div>
            <div className="mt-1 flex items-end gap-2">
              <span className="text-2xl font-semibold text-text-primary">{totalDocuments}</span>
              <span className="pb-1 text-xs text-text-tertiary">份入库文档</span>
            </div>
          </div>
          <div className="rounded-lg border border-divider-subtle bg-background-default px-4 py-3">
            <div className="text-xs text-text-tertiary">可下载原文</div>
            <div className="mt-1 flex items-end gap-2">
              <span className="text-2xl font-semibold text-text-primary">{downloadableDocuments}</span>
              <span className="pb-1 text-xs text-text-tertiary">份上传文件副本</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-4 px-8 py-5">
        <aside className="hidden w-72 shrink-0 flex-col rounded-lg border border-divider-subtle bg-background-default md:flex">
          <div className="border-b border-divider-subtle px-4 py-3">
            <div className="text-sm font-semibold text-text-primary">知识库筛选</div>
            <div className="mt-1 text-xs text-text-tertiary">
              当前：
              {selectedDatasetName}
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            <button
              type="button"
              className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm ${datasetId === 'all' ? 'bg-state-accent-hover text-text-accent' : 'text-text-secondary hover:bg-background-default-hover'}`}
              onClick={() => setDatasetId('all')}
            >
              <span className="truncate">全部知识库</span>
              <span className="ml-2 rounded bg-background-section px-1.5 py-0.5 text-xs text-text-tertiary">{totalDocuments}</span>
            </button>
            {(data?.datasets ?? []).map(dataset => (
              <button
                key={dataset.id}
                type="button"
                className={`mt-1 flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm ${datasetId === dataset.id ? 'bg-state-accent-hover text-text-accent' : 'text-text-secondary hover:bg-background-default-hover'}`}
                onClick={() => setDatasetId(dataset.id)}
              >
                <span className="truncate">{dataset.name}</span>
                <span className="ml-2 rounded bg-background-section px-1.5 py-0.5 text-xs text-text-tertiary">{dataset.document_count}</span>
              </button>
            ))}
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col rounded-lg border border-divider-subtle bg-background-default">
          <div className="flex flex-wrap items-center gap-3 border-b border-divider-subtle px-4 py-3">
            <div className="relative min-w-64 flex-1">
              <RiSearchLine className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-quaternary" />
              <input
                value={keyword}
                onChange={event => setKeyword(event.target.value)}
                placeholder="搜索文档名或知识库"
                className="border-components-input-border h-9 w-full rounded-lg border bg-components-input-bg-normal pr-3 pl-9 text-sm text-text-primary outline-none placeholder:text-text-quaternary focus:border-components-input-border-active"
              />
            </div>
            <select
              value={datasetId}
              onChange={event => setDatasetId(event.target.value)}
              className="border-components-input-border h-9 rounded-lg border bg-components-input-bg-normal px-3 text-sm text-text-secondary outline-none md:hidden"
            >
              <option value="all">全部知识库</option>
              {(data?.datasets ?? []).map(dataset => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}
            </select>
            <div className="text-sm text-text-tertiary">
              显示
              {' '}
              {filteredDocuments.length}
              {' '}
              /
              {' '}
              {totalDocuments}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-auto">
            {filteredDocuments.length === 0
              ? (
                  <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                    <RiFileList3Line className="size-10 text-text-quaternary" />
                    <div className="mt-3 text-sm font-medium text-text-secondary">没有匹配的文档</div>
                    <div className="mt-1 text-xs text-text-tertiary">换一个关键词或选择全部知识库。</div>
                  </div>
                )
              : (
                  <table className="w-full min-w-[980px] border-collapse text-sm">
                    <thead className="sticky top-0 z-10 border-b border-divider-subtle bg-background-default text-xs font-medium text-text-tertiary">
                      <tr>
                        <th className="w-[34%] px-4 py-3 text-left">文档</th>
                        <th className="w-[22%] px-4 py-3 text-left">知识库</th>
                        <th className="w-[10%] px-4 py-3 text-left">字符数</th>
                        <th className="w-[10%] px-4 py-3 text-left">召回</th>
                        <th className="w-[12%] px-4 py-3 text-left">状态</th>
                        <th className="w-[12%] px-4 py-3 text-left">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDocuments.map((doc) => {
                        const status = doc.display_status || doc.indexing_status
                        return (
                          <tr key={`${doc.dataset.id}-${doc.id}`} className="border-b border-divider-subtle hover:bg-background-default-hover">
                            <td className="px-4 py-3 align-top">
                              <div className="flex items-start gap-2">
                                <RiFileList3Line className="mt-0.5 size-4 shrink-0 text-text-tertiary" />
                                <div className="min-w-0">
                                  <div className="truncate font-medium text-text-primary" title={doc.name}>{doc.name}</div>
                                  <div className="mt-1 text-xs text-text-tertiary">
                                    上传时间：
                                    {formatTime(doc.created_at)}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="px-4 py-3 align-top">
                              <div className="flex min-w-0 items-center gap-2 text-text-secondary">
                                <RiDatabase2Line className="size-4 shrink-0 text-text-tertiary" />
                                <span className="truncate" title={doc.dataset.name}>{doc.dataset.name}</span>
                              </div>
                            </td>
                            <td className="px-4 py-3 align-top text-text-secondary">{doc.word_count?.toLocaleString() || 0}</td>
                            <td className="px-4 py-3 align-top text-text-secondary">{doc.hit_count?.toLocaleString() || 0}</td>
                            <td className="px-4 py-3 align-top">
                              <span className={`inline-flex rounded-md px-2 py-1 text-xs font-medium ${statusClassName(status)}`}>
                                {statusLabel[status] || status}
                              </span>
                            </td>
                            <td className="px-4 py-3 align-top">
                              <div className="flex items-center gap-2">
                                <Link
                                  href={`/datasets/${doc.dataset.id}/documents/${doc.id}`}
                                  className="inline-flex h-8 items-center gap-1 rounded-md border border-components-button-secondary-border bg-components-button-secondary-bg px-2.5 text-xs font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover"
                                >
                                  分段
                                  <RiArrowRightLine className="size-3.5" />
                                </Link>
                                <button
                                  type="button"
                                  disabled={!isDownloadable(doc) || previewingId === doc.id}
                                  className="inline-flex h-8 items-center gap-1 rounded-md border border-components-button-secondary-border bg-components-button-secondary-bg px-2.5 text-xs font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover disabled:cursor-not-allowed disabled:opacity-50"
                                  onClick={() => handlePreview(doc)}
                                >
                                  {previewingId === doc.id ? '打开中' : '预览原文'}
                                  <RiArrowRightLine className="size-3.5" />
                                </button>
                                <button
                                  type="button"
                                  disabled={!isDownloadable(doc) || downloadingId === doc.id}
                                  className="inline-flex h-8 items-center gap-1 rounded-md border border-components-button-secondary-border bg-components-button-secondary-bg px-2.5 text-xs font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover disabled:cursor-not-allowed disabled:opacity-50"
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

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-divider-subtle px-4 py-3 text-xs text-text-tertiary">
            <span>
              可用文档
              {availableDocuments}
              {' '}
              份
            </span>
            <span>“分段”查看入库后的 Chunk；“预览原文”会尝试在浏览器打开原始上传文件。</span>
          </div>
        </main>
      </div>
    </div>
  )
}

export default DocumentManagement
