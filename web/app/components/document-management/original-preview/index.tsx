'use client'

import type { DocumentOfficePreviewConfigResponse } from '@/service/datasets'
import type { GeneratedAssetPreviewConfigResponse } from '@/service/generated-files'
import { RiDownload2Line, RiErrorWarningLine, RiFileList3Line, RiRefreshLine } from '@remixicon/react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import Loading from '@/app/components/base/loading'
import useDocumentTitle from '@/hooks/use-document-title'
import { useSearchParams } from '@/next/navigation'
import { fetchDocumentConvertedPreviewBlob, fetchDocumentOfficePreviewConfig } from '@/service/datasets'
import { fetchGeneratedAssetPreviewConfig } from '@/service/generated-files'
import { downloadUrl } from '@/utils/download'

type PreviewData = DocumentOfficePreviewConfigResponse | GeneratedAssetPreviewConfigResponse

const isImage = (fileType: string) => ['bmp', 'gif', 'jpeg', 'jpg', 'png', 'svg', 'webp'].includes(fileType)
const isPlainText = (fileType: string) => ['csv', 'json', 'log', 'md', 'txt', 'xml', 'yaml', 'yml'].includes(fileType)

const getAssetMetadataUrl = (asset: GeneratedAssetPreviewConfigResponse, key: string) => {
  const value = asset.asset_metadata?.[key]
  return typeof value === 'string' ? value : ''
}

const ConvertedPdfPreview = ({ data }: { data: PreviewData }) => {
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

const RemoteMediaError = ({
  name,
  onRetry,
  sourceUrl,
}: {
  name: string
  onRetry: () => void
  sourceUrl: string
}) => (
  <div className="flex h-full w-full flex-col items-center justify-center gap-3 bg-background-section px-6 text-center">
    <RiErrorWarningLine className="size-10 text-text-warning" />
    <div className="text-sm font-medium text-text-secondary">源文件暂不可用</div>
    <div className="flex items-center gap-2">
      <button
        type="button"
        className="inline-flex h-9 items-center gap-2 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-sm font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover"
        onClick={onRetry}
      >
        <RiRefreshLine className="size-4" />
        重试
      </button>
      <button
        type="button"
        className="inline-flex h-9 items-center gap-2 rounded-lg border border-components-button-secondary-border bg-components-button-secondary-bg px-3 text-sm font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover"
        onClick={() => downloadUrl({ url: sourceUrl, fileName: name, target: /^https?:\/\//.test(sourceUrl) ? '_blank' : undefined })}
      >
        <RiDownload2Line className="size-4" />
        下载源文件
      </button>
    </div>
  </div>
)

const RemoteVideoPreview = ({
  asset,
  data,
  previewUrl,
}: {
  asset: GeneratedAssetPreviewConfigResponse
  data: PreviewData
  previewUrl: string
}) => {
  const [failed, setFailed] = useState(false)
  const [retryKey, setRetryKey] = useState(0)
  const supportingImages = [
    { label: '场景图', url: getAssetMetadataUrl(asset, 'scene_image_url') },
    { label: '角色图', url: getAssetMetadataUrl(asset, 'character_image_url') },
  ].filter(item => item.url)

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto bg-black p-4">
      <div className="flex min-h-[240px] flex-1 items-center justify-center">
        {failed
          ? (
              <RemoteMediaError
                name={data.name}
                sourceUrl={data.download_url || previewUrl}
                onRetry={() => {
                  setFailed(false)
                  setRetryKey(key => key + 1)
                }}
              />
            )
          : (
              <video
                key={retryKey}
                aria-label={data.name}
                className="max-h-full max-w-full bg-black"
                controls
                poster={asset.thumbnail_url || undefined}
                preload="metadata"
                src={previewUrl}
                onError={() => setFailed(true)}
              />
            )}
      </div>
      {supportingImages.length > 0 && (
        <div className="grid shrink-0 grid-cols-2 gap-3">
          {supportingImages.map(image => (
            <figure key={image.label} className="overflow-hidden rounded-lg border border-white/15 bg-white/5">
              <img src={image.url} alt={image.label} loading="lazy" className="aspect-video w-full object-cover" />
              <figcaption className="px-2.5 py-2 text-xs text-white/70">{image.label}</figcaption>
            </figure>
          ))}
        </div>
      )}
    </div>
  )
}

const RemoteAudioPreview = ({ data, previewUrl }: { data: PreviewData, previewUrl: string }) => {
  const [failed, setFailed] = useState(false)
  const [retryKey, setRetryKey] = useState(0)

  if (failed) {
    return (
      <RemoteMediaError
        name={data.name}
        sourceUrl={data.download_url || previewUrl}
        onRetry={() => {
          setFailed(false)
          setRetryKey(key => key + 1)
        }}
      />
    )
  }

  return (
    <div className="flex h-full items-center justify-center bg-background-section p-6">
      <audio key={retryKey} aria-label={data.name} controls preload="metadata" src={previewUrl} className="w-full max-w-2xl" onError={() => setFailed(true)} />
    </div>
  )
}

const ImagePreview = ({ data, previewUrl }: { data: PreviewData, previewUrl: string }) => {
  const [failed, setFailed] = useState(false)
  const [retryKey, setRetryKey] = useState(0)

  if (failed) {
    return (
      <RemoteMediaError
        name={data.name}
        sourceUrl={data.download_url || previewUrl}
        onRetry={() => {
          setFailed(false)
          setRetryKey(key => key + 1)
        }}
      />
    )
  }

  return (
    <div className="flex h-full items-center justify-center overflow-auto bg-background-section p-6">
      <img
        key={retryKey}
        src={previewUrl}
        alt={data.name}
        className="max-h-full max-w-full object-contain"
        onError={() => setFailed(true)}
      />
    </div>
  )
}

const NativePreview = ({ data }: { data: PreviewData }) => {
  if (data.preview_kind === 'converted_pdf')
    return <ConvertedPdfPreview key={data.preview_url} data={data} />

  const asset = data as GeneratedAssetPreviewConfigResponse
  const extension = asset.extension || data.original_file_type || data.file_type
  const previewUrl = asset.storage_type === 'remote_url'
    ? asset.source_url || data.preview_url
    : data.preview_url

  if (data.file_type === 'video')
    return <RemoteVideoPreview data={data} asset={asset} previewUrl={previewUrl} />

  if (data.file_type === 'audio')
    return <RemoteAudioPreview data={data} previewUrl={previewUrl} />

  if (data.file_type === 'image' || isImage(extension)) {
    return <ImagePreview data={data} previewUrl={previewUrl} />
  }

  if (extension === 'pdf' || asset.mime_type === 'application/pdf')
    return <iframe src={data.preview_url} title={data.name} className="h-full w-full border-0 bg-white" />

  if (isPlainText(extension))
    return <iframe src={data.preview_url} title={data.name} className="h-full w-full border-0 bg-white" />

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-background-section px-6 text-center">
      <RiFileList3Line className="size-10 text-text-quaternary" />
      <div className="text-sm font-medium text-text-secondary">当前文件类型暂不支持在线预览</div>
      <button
        type="button"
        className="inline-flex h-9 items-center gap-2 rounded-lg bg-components-button-primary-bg px-3 text-sm font-medium text-components-button-primary-text hover:bg-components-button-primary-bg-hover"
        onClick={() => downloadUrl({
          url: data.download_url,
          fileName: data.name,
          target: data.mode === 'remote' ? '_blank' : undefined,
        })}
      >
        <RiDownload2Line className="size-4" />
        下载原文
      </button>
    </div>
  )
}

const previewLabel = (data: PreviewData) => {
  if (data.preview_kind === 'converted_pdf')
    return 'PDF 转换预览'
  if (data.file_type === 'video')
    return '视频预览'
  if (data.file_type === 'audio')
    return '音频预览'
  if (data.preview_kind === 'unavailable')
    return '源文件暂不可用'
  if (data.preview_kind === 'unsupported')
    return '仅支持下载原文'
  return '原生在线预览'
}

const DocumentOriginalPreview = () => {
  useDocumentTitle('资产预览')
  const searchParams = useSearchParams()
  const datasetId = searchParams.get('datasetId') || ''
  const documentId = searchParams.get('documentId') || ''
  const generatedAssetId = searchParams.get('generatedAssetId') || searchParams.get('generatedFileId') || ''

  const { data, isLoading, refetch, isFetching, error } = useQuery<PreviewData>({
    queryKey: ['asset-preview', datasetId, documentId, generatedAssetId],
    queryFn: () => generatedAssetId
      ? fetchGeneratedAssetPreviewConfig(generatedAssetId)
      : fetchDocumentOfficePreviewConfig({ datasetId, documentId }),
    enabled: !!generatedAssetId || (!!datasetId && !!documentId),
    staleTime: 30 * 1000,
  })

  if (!generatedAssetId && (!datasetId || !documentId)) {
    return (
      <div className="flex h-full items-center justify-center bg-background-body text-sm text-text-tertiary">
        缺少资产或文档参数
      </div>
    )
  }

  if (isLoading)
    return <Loading type="app" />

  if (error || !data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-background-body px-6 text-center">
        <RiErrorWarningLine className="size-10 text-text-warning" />
        <div className="text-sm font-medium text-text-secondary">资产预览加载失败</div>
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
          onClick={() => downloadUrl({
            url: data.download_url,
            fileName: data.name,
            target: data.mode === 'remote' ? '_blank' : undefined,
          })}
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
