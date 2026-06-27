'use client'

import type { DocumentOfficePreviewConfigResponse } from '@/service/datasets'
import { RiDownload2Line, RiErrorWarningLine, RiFileList3Line, RiRefreshLine } from '@remixicon/react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import Loading from '@/app/components/base/loading'
import useDocumentTitle from '@/hooks/use-document-title'
import { useSearchParams } from '@/next/navigation'
import { fetchDocumentConvertedPreviewBlob, fetchDocumentOfficePreviewConfig } from '@/service/datasets'
import { downloadUrl } from '@/utils/download'

const isImage = (fileType: string) => ['bmp', 'gif', 'jpeg', 'jpg', 'png', 'svg', 'webp'].includes(fileType)
const isPlainText = (fileType: string) => ['csv', 'json', 'log', 'md', 'txt', 'xml', 'yaml', 'yml'].includes(fileType)

const ConvertedPdfPreview = ({ data }: { data: DocumentOfficePreviewConfigResponse }) => {
  const [blobUrl, setBlobUrl] = useState('')
  const [error, setError] = useState(false)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    let disposed = false
    let objectUrl = ''

    fetchDocumentConvertedPreviewBlob(data.preview_url)
      .then((blob) => {
        if (disposed)
          return
        objectUrl = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
        setBlobUrl(objectUrl)
      })
      .catch(() => {
        if (!disposed)
          setError(true)
      })

    return () => {
      disposed = true
      if (objectUrl)
        URL.revokeObjectURL(objectUrl)
    }
  }, [data.preview_url, retryKey])

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-background-section px-6 text-center">
        <RiErrorWarningLine className="size-10 text-text-warning" />
        <div className="text-sm font-medium text-text-secondary">PDF 转换预览加载失败</div>
        <button
          type="button"
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-sm font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover"
          onClick={() => {
            setBlobUrl('')
            setError(false)
            setRetryKey(key => key + 1)
          }}
        >
          <RiRefreshLine className="size-4" />
          重试
        </button>
      </div>
    )
  }

  if (!blobUrl)
    return <Loading type="app" />

  return <iframe src={blobUrl} title={data.name} className="h-full w-full border-0 bg-white" />
}

const NativePreview = ({ data }: { data: DocumentOfficePreviewConfigResponse }) => {
  if (data.preview_kind === 'converted_pdf')
    return <ConvertedPdfPreview key={data.preview_url} data={data} />

  if (isImage(data.file_type)) {
    return (
      <div className="flex h-full items-center justify-center overflow-auto bg-background-section p-6">
        <img src={data.preview_url} alt={data.name} className="max-h-full max-w-full object-contain" />
      </div>
    )
  }

  if (data.file_type === 'pdf')
    return <iframe src={data.preview_url} title={data.name} className="h-full w-full border-0 bg-white" />

  if (isPlainText(data.file_type))
    return <iframe src={data.preview_url} title={data.name} className="h-full w-full border-0 bg-white" />

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-background-section px-6 text-center">
      <RiFileList3Line className="size-10 text-text-quaternary" />
      <div className="text-sm font-medium text-text-secondary">当前文件类型暂不支持在线预览</div>
      <button
        type="button"
        className="inline-flex h-9 items-center gap-2 rounded-lg bg-components-button-primary-bg px-3 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover"
        onClick={() => downloadUrl({ url: data.download_url, fileName: data.name })}
      >
        <RiDownload2Line className="size-4" />
        下载原文
      </button>
    </div>
  )
}

const previewLabel = (data: DocumentOfficePreviewConfigResponse) => {
  if (data.preview_kind === 'converted_pdf')
    return 'PDF 转换预览'
  if (data.preview_kind === 'unsupported')
    return '仅支持下载原文'
  return '原生在线预览'
}

const DocumentOriginalPreview = () => {
  useDocumentTitle('原文预览')
  const searchParams = useSearchParams()
  const datasetId = searchParams.get('datasetId') || ''
  const documentId = searchParams.get('documentId') || ''

  const { data, isLoading, refetch, isFetching, error } = useQuery({
    queryKey: ['document-original-preview', datasetId, documentId],
    queryFn: () => fetchDocumentOfficePreviewConfig({ datasetId, documentId }),
    enabled: !!datasetId && !!documentId,
    staleTime: 30 * 1000,
  })

  if (!datasetId || !documentId) {
    return (
      <div className="flex h-full items-center justify-center bg-background-body text-sm text-text-tertiary">
        缺少文档参数
      </div>
    )
  }

  if (isLoading)
    return <Loading type="app" />

  if (error || !data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-background-body px-6 text-center">
        <RiErrorWarningLine className="size-10 text-text-warning" />
        <div className="text-sm font-medium text-text-secondary">原文预览加载失败</div>
        <button
          type="button"
          disabled={isFetching}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-sm font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover disabled:cursor-not-allowed disabled:opacity-60"
          onClick={() => refetch()}
        >
          <RiRefreshLine className="size-4" />
          重试
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col bg-background-body">
      <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-divider-subtle bg-background-default px-5">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-text-primary" title={data.name}>{data.name}</div>
          <div className="text-xs text-text-tertiary">{previewLabel(data)}</div>
        </div>
        <button
          type="button"
          className="inline-flex h-9 shrink-0 items-center gap-2 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-sm font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover"
          onClick={() => downloadUrl({ url: data.download_url, fileName: data.name })}
        >
          <RiDownload2Line className="size-4" />
          下载
        </button>
      </div>
      <div className="min-h-0 flex-1">
        <NativePreview data={data} />
      </div>
    </div>
  )
}

export default DocumentOriginalPreview
