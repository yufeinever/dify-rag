'use client'

import type { DocumentOfficePreviewConfigResponse } from '@/service/datasets'
import { RiDownload2Line, RiErrorWarningLine, RiFileList3Line, RiRefreshLine } from '@remixicon/react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import Loading from '@/app/components/base/loading'
import useDocumentTitle from '@/hooks/use-document-title'
import { useSearchParams } from '@/next/navigation'
import { fetchDocumentOfficePreviewConfig } from '@/service/datasets'
import { downloadUrl } from '@/utils/download'

type OnlyOfficeEditor = { destroyEditor?: () => void }

type OnlyOfficeDocsAPI = {
  DocEditor: new (elementId: string, config: Record<string, unknown>) => OnlyOfficeEditor
}

declare global {
  // eslint-disable-next-line ts/consistent-type-definitions
  interface Window {
    DocsAPI?: OnlyOfficeDocsAPI
  }
}

const OFFICE_SCRIPT_ID = 'onlyoffice-docs-api'

const loadScript = (src: string) => {
  const existing = document.getElementById(OFFICE_SCRIPT_ID) as HTMLScriptElement | null
  if (existing) {
    if (window.DocsAPI)
      return Promise.resolve()

    return new Promise<void>((resolve, reject) => {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error('OnlyOffice script failed to load')), { once: true })
    })
  }

  return new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.id = OFFICE_SCRIPT_ID
    script.src = src
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('OnlyOffice script failed to load'))
    document.body.appendChild(script)
  })
}

const isImage = (fileType: string) => ['bmp', 'gif', 'jpeg', 'jpg', 'png', 'svg', 'webp'].includes(fileType)
const isPlainText = (fileType: string) => ['csv', 'json', 'log', 'md', 'txt', 'xml'].includes(fileType)

const NativePreview = ({ data }: { data: DocumentOfficePreviewConfigResponse }) => {
  if (isImage(data.file_type)) {
    return (
      <div className="flex h-full items-center justify-center overflow-auto bg-background-section p-6">
        <img src={data.preview_url} alt={data.name} className="max-h-full max-w-full object-contain" />
      </div>
    )
  }

  if (isPlainText(data.file_type) || data.file_type === 'pdf') {
    return <iframe src={data.preview_url} title={data.name} className="h-full w-full border-0 bg-white" />
  }

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

const OnlyOfficePreview = ({ data }: { data: DocumentOfficePreviewConfigResponse }) => {
  const editorRef = useRef<{ destroyEditor?: () => void } | null>(null)
  const [error, setError] = useState('')
  const scriptSrc = useMemo(() => {
    const baseUrl = (data.document_server_url || '').replace(/\/$/, '')
    return `${baseUrl}/web-apps/apps/api/documents/api.js`
  }, [data.document_server_url])

  useEffect(() => {
    let disposed = false

    const mountEditor = async () => {
      if (!data.config)
        return

      setError('')
      try {
        await loadScript(scriptSrc)
        if (disposed)
          return

        if (!window.DocsAPI)
          throw new Error('OnlyOffice DocsAPI is unavailable')

        editorRef.current?.destroyEditor?.()
        editorRef.current = new window.DocsAPI.DocEditor('onlyoffice-document-editor', data.config)
      }
      catch {
        if (!disposed)
          setError('OnlyOffice 预览组件加载失败')
      }
    }

    mountEditor()

    return () => {
      disposed = true
      editorRef.current?.destroyEditor?.()
      editorRef.current = null
    }
  }, [data.config, scriptSrc])

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-background-section px-6 text-center">
        <RiErrorWarningLine className="size-10 text-text-warning" />
        <div className="text-sm font-medium text-text-secondary">{error}</div>
        <button
          type="button"
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-sm font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover"
          onClick={() => window.location.reload()}
        >
          <RiRefreshLine className="size-4" />
          重试
        </button>
      </div>
    )
  }

  return <div id="onlyoffice-document-editor" className="h-full w-full bg-white" />
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
          <div className="text-xs text-text-tertiary">{data.mode === 'onlyoffice' ? 'OnlyOffice 在线预览' : '原生在线预览'}</div>
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
        {data.mode === 'onlyoffice' ? <OnlyOfficePreview data={data} /> : <NativePreview data={data} />}
      </div>
    </div>
  )
}

export default DocumentOriginalPreview
