'use client'

import type { ChangeEvent } from 'react'
import { cn } from '@langgenius/dify-ui/cn'
import JSZip from 'jszip'
import { PDFDocument } from 'pdf-lib'
import { useCallback, useMemo, useRef, useState } from 'react'
import useDocumentTitle from '@/hooks/use-document-title'
import { useRouter } from '@/next/navigation'

type SupportedType = 'pptx' | 'pdf'

type CompressStage = 'idle' | 'reading' | 'compressing' | 'done' | 'error' | 'cancelled'

type Report = {
  fileName: string
  type: SupportedType
  originalSize: number
  outputSize: number
  elapsedMs: number
  totalItems: number
  processedItems: number
  compressedItems: number
  warnings: string[]
}

type ProgressState = {
  stage: CompressStage
  message: string
  current: number
  total: number
}

type CompressOptions = {
  maxLongEdge: number
  jpegQuality: number
}

class CompressionCancelled extends Error {
  constructor() {
    super('压缩已取消')
    this.name = 'CompressionCancelled'
  }
}

const DEFAULT_OPTIONS: CompressOptions = {
  maxLongEdge: 1800,
  jpegQuality: 0.82,
}

const imageFilePattern = /^ppt\/media\/.*\.(?:jpe?g|png)$/i

const fileTypeLabel: Record<SupportedType, string> = {
  pptx: 'PPTX 图片压缩',
  pdf: 'PDF 扫描件压缩',
}

const formatBytes = (size: number) => {
  if (!size)
    return '0 B'

  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1)
  return `${(size / 1024 ** index).toFixed(index === 0 ? 0 : 2)} ${units[index]}`
}

const formatElapsed = (ms: number) => {
  if (ms < 1000)
    return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(1)} 秒`
}

const getSupportedType = (file: File): SupportedType | undefined => {
  const name = file.name.toLowerCase()
  if (name.endsWith('.pptx'))
    return 'pptx'
  if (name.endsWith('.pdf'))
    return 'pdf'
}

const getOutputName = (fileName: string) => {
  const dotIndex = fileName.lastIndexOf('.')
  if (dotIndex === -1)
    return `${fileName}_compressed`

  return `${fileName.slice(0, dotIndex)}_compressed${fileName.slice(dotIndex)}`
}

const blobToArrayBuffer = (blob: Blob) => blob.arrayBuffer()

const canvasToBlob = (canvas: HTMLCanvasElement, type: string, quality?: number) => {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('浏览器无法生成压缩图片'))
        return
      }
      resolve(blob)
    }, type, quality)
  })
}

const downloadBlob = (blob: Blob, fileName: string) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.rel = 'noreferrer'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 3000)
}

const assertNotCancelled = (isActive: () => boolean) => {
  if (!isActive())
    throw new CompressionCancelled()
}

const compressImageBlob = async (
  blob: Blob,
  extension: string,
  options: CompressOptions,
) => {
  const bitmap = await createImageBitmap(blob)
  const sourceWidth = bitmap.width
  const sourceHeight = bitmap.height
  const longEdge = Math.max(sourceWidth, sourceHeight)
  const scale = longEdge > options.maxLongEdge ? options.maxLongEdge / longEdge : 1
  const targetWidth = Math.max(1, Math.round(sourceWidth * scale))
  const targetHeight = Math.max(1, Math.round(sourceHeight * scale))
  const canvas = document.createElement('canvas')
  canvas.width = targetWidth
  canvas.height = targetHeight
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    bitmap.close()
    throw new Error('当前浏览器不支持 Canvas 压缩')
  }
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(bitmap, 0, 0, targetWidth, targetHeight)
  bitmap.close()

  const isPng = extension.toLowerCase() === 'png'
  const outputBlob = await canvasToBlob(
    canvas,
    isPng ? 'image/png' : 'image/jpeg',
    isPng ? undefined : options.jpegQuality,
  )

  canvas.width = 0
  canvas.height = 0

  return {
    blob: outputBlob,
    resized: targetWidth !== sourceWidth || targetHeight !== sourceHeight,
  }
}

const compressPptx = async (
  file: File,
  options: CompressOptions,
  isActive: () => boolean,
  updateProgress: (state: ProgressState) => void,
) => {
  updateProgress({ stage: 'reading', message: '正在读取 PPTX 压缩包', current: 0, total: 1 })
  const zip = await JSZip.loadAsync(await file.arrayBuffer())
  assertNotCancelled(isActive)

  const mediaFiles = Object.values(zip.files)
    .filter(entry => !entry.dir && imageFilePattern.test(entry.name))

  const warnings: string[] = []
  let processedItems = 0
  let compressedItems = 0

  for (const entry of mediaFiles) {
    assertNotCancelled(isActive)
    processedItems += 1
    updateProgress({
      stage: 'compressing',
      message: `正在压缩 PPT 图片 ${processedItems}/${mediaFiles.length}`,
      current: processedItems,
      total: mediaFiles.length,
    })

    const extension = entry.name.split('.').pop() || ''
    try {
      const originalBlob = await entry.async('blob')
      const result = await compressImageBlob(originalBlob, extension, options)
      if (result.blob.size < originalBlob.size * 0.98) {
        zip.file(entry.name, await blobToArrayBuffer(result.blob), {
          binary: true,
          date: entry.date,
        })
        compressedItems += 1
      }
    }
    catch (error) {
      warnings.push(`${entry.name} 未压缩：${error instanceof Error ? error.message : '图片解码失败'}`)
    }
  }

  updateProgress({ stage: 'compressing', message: '正在重新打包 PPTX', current: mediaFiles.length, total: mediaFiles.length })
  const outputBlob = await zip.generateAsync({
    type: 'blob',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
  })

  return {
    blob: outputBlob,
    totalItems: mediaFiles.length,
    processedItems,
    compressedItems,
    warnings,
  }
}

type PdfJsModule = {
  GlobalWorkerOptions: { workerSrc: string }
  getDocument: (options: { data: ArrayBuffer }) => { promise: Promise<PdfDocumentProxy> }
}

const PDFJS_STATIC_BASE = '/vendor/pdfjs-4.4.168'

const loadPdfJs = async () => {
  const pdfjsUrl = `${PDFJS_STATIC_BASE}/pdf.mjs`
  const pdfjs = await import(/* webpackIgnore: true */ pdfjsUrl) as PdfJsModule
  pdfjs.GlobalWorkerOptions.workerSrc = `${PDFJS_STATIC_BASE}/pdf.worker.mjs`
  return pdfjs
}

type PdfViewport = {
  width: number
  height: number
}

type PdfPageProxy = {
  getTextContent: () => Promise<{ items: unknown[] }>
  getViewport: (options: { scale: number }) => PdfViewport
  render: (options: { canvasContext: CanvasRenderingContext2D, viewport: PdfViewport }) => { promise: Promise<void> }
  cleanup: () => void
}

type PdfDocumentProxy = {
  numPages: number
  getPage: (pageNumber: number) => Promise<PdfPageProxy>
  destroy: () => Promise<void>
}

const detectPdfTextLayer = async (pdf: PdfDocumentProxy) => {
  const pagesToCheck = Math.min(pdf.numPages, 3)
  let textItems = 0
  for (let index = 1; index <= pagesToCheck; index += 1) {
    const page = await pdf.getPage(index)
    const textContent = await page.getTextContent()
    textItems += textContent.items.length
    page.cleanup()
  }
  return textItems > 20
}

const compressPdf = async (
  file: File,
  options: CompressOptions,
  allowTextPdfRasterize: boolean,
  isActive: () => boolean,
  updateProgress: (state: ProgressState) => void,
) => {
  updateProgress({ stage: 'reading', message: '正在读取 PDF', current: 0, total: 1 })
  const pdfjs = await loadPdfJs()
  const inputBytes = await file.arrayBuffer()
  const pdf = await pdfjs.getDocument({ data: inputBytes }).promise as unknown as PdfDocumentProxy
  assertNotCancelled(isActive)

  const warnings: string[] = []
  const hasTextLayer = await detectPdfTextLayer(pdf)
  if (hasTextLayer && !allowTextPdfRasterize)
    throw new Error('这个 PDF 可能包含可复制文字层。Demo 默认不压缩文本型 PDF；如确认它是扫描件或允许转成图片 PDF，请勾选确认项。')
  if (hasTextLayer)
    warnings.push('检测到文字层：本次输出会变成图片 PDF，可能无法复制原文字。')

  const outputPdf = await PDFDocument.create()
  let processedItems = 0

  for (let pageIndex = 1; pageIndex <= pdf.numPages; pageIndex += 1) {
    assertNotCancelled(isActive)
    updateProgress({
      stage: 'compressing',
      message: `正在渲染 PDF 第 ${pageIndex}/${pdf.numPages} 页`,
      current: pageIndex,
      total: pdf.numPages,
    })
    const page = await pdf.getPage(pageIndex)
    const baseViewport = page.getViewport({ scale: 1 })
    const renderScale = Math.max(1, Math.min(3, options.maxLongEdge / Math.max(baseViewport.width, baseViewport.height)))
    const viewport = page.getViewport({ scale: renderScale })
    const canvas = document.createElement('canvas')
    canvas.width = Math.ceil(viewport.width)
    canvas.height = Math.ceil(viewport.height)
    const canvasContext = canvas.getContext('2d', { alpha: false })
    if (!canvasContext)
      throw new Error('当前浏览器不支持 PDF Canvas 渲染')

    canvasContext.fillStyle = '#fff'
    canvasContext.fillRect(0, 0, canvas.width, canvas.height)
    await page.render({ canvasContext, viewport }).promise
    const jpegBlob = await canvasToBlob(canvas, 'image/jpeg', options.jpegQuality)
    const jpegImage = await outputPdf.embedJpg(await jpegBlob.arrayBuffer())
    const outputPage = outputPdf.addPage([baseViewport.width, baseViewport.height])
    outputPage.drawImage(jpegImage, {
      x: 0,
      y: 0,
      width: baseViewport.width,
      height: baseViewport.height,
    })
    processedItems += 1
    page.cleanup()
    canvas.width = 0
    canvas.height = 0
  }

  const outputBytes = await outputPdf.save({ useObjectStreams: true })
  await pdf.destroy()

  const outputArrayBuffer = outputBytes.buffer.slice(
    outputBytes.byteOffset,
    outputBytes.byteOffset + outputBytes.byteLength,
  ) as ArrayBuffer

  return {
    blob: new Blob([outputArrayBuffer], { type: 'application/pdf' }),
    totalItems: pdf.numPages,
    processedItems,
    compressedItems: processedItems,
    warnings,
  }
}

const Metric = ({ label, value }: { label: string, value: string }) => {
  return (
    <div className="rounded-lg bg-white/70 p-3">
      <div className="text-xs text-text-tertiary">{label}</div>
      <div className="mt-1 text-base font-semibold text-text-primary">{value}</div>
    </div>
  )
}

const LocalMaterialCompressDemo = () => {
  const router = useRouter()
  useDocumentTitle('本地材料压缩 Demo')

  const [file, setFile] = useState<File | undefined>()
  const [error, setError] = useState('')
  const [report, setReport] = useState<Report | undefined>()
  const [progress, setProgress] = useState<ProgressState>({ stage: 'idle', message: '请选择 PPTX 或 PDF 文件', current: 0, total: 0 })
  const [maxLongEdge, setMaxLongEdge] = useState(DEFAULT_OPTIONS.maxLongEdge)
  const [jpegQuality, setJpegQuality] = useState(DEFAULT_OPTIONS.jpegQuality)
  const [allowTextPdfRasterize, setAllowTextPdfRasterize] = useState(false)

  const activeJobRef = useRef(0)

  const fileType = useMemo(() => file ? getSupportedType(file) : undefined, [file])
  const isWorking = progress.stage === 'reading' || progress.stage === 'compressing'
  const progressPercent = progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : 0

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0]
    setError('')
    setReport(undefined)
    setProgress({ stage: 'idle', message: '请选择 PPTX 或 PDF 文件', current: 0, total: 0 })
    if (!selected) {
      setFile(undefined)
      return
    }
    if (!getSupportedType(selected)) {
      setFile(undefined)
      setError('当前 Demo 只支持 .pptx 和 .pdf 文件。老格式 .ppt 请先另存为 .pptx。')
      return
    }
    setFile(selected)
  }

  const handleCancel = () => {
    activeJobRef.current += 1
    setProgress(prev => ({ ...prev, stage: 'cancelled', message: '已取消，本地文件没有上传' }))
  }

  const handleCompress = useCallback(async () => {
    if (!file || !fileType || isWorking)
      return

    const jobId = activeJobRef.current + 1
    activeJobRef.current = jobId
    const startedAt = performance.now()
    const isActive = () => activeJobRef.current === jobId
    const options = { maxLongEdge, jpegQuality }

    setError('')
    setReport(undefined)
    setProgress({ stage: 'reading', message: '正在本地读取文件', current: 0, total: 1 })

    try {
      const result = fileType === 'pptx'
        ? await compressPptx(file, options, isActive, setProgress)
        : await compressPdf(file, options, allowTextPdfRasterize, isActive, setProgress)

      assertNotCancelled(isActive)
      const outputName = getOutputName(file.name)
      downloadBlob(result.blob, outputName)
      const elapsedMs = performance.now() - startedAt
      setReport({
        fileName: outputName,
        type: fileType,
        originalSize: file.size,
        outputSize: result.blob.size,
        elapsedMs,
        totalItems: result.totalItems,
        processedItems: result.processedItems,
        compressedItems: result.compressedItems,
        warnings: result.warnings,
      })
      setProgress({ stage: 'done', message: '压缩完成，已触发浏览器下载', current: result.totalItems, total: result.totalItems })
    }
    catch (err) {
      if (err instanceof CompressionCancelled) {
        setProgress(prev => ({ ...prev, stage: 'cancelled', message: '已取消，本地文件没有上传' }))
        return
      }
      setError(err instanceof Error ? err.message : '压缩失败')
      setProgress(prev => ({ ...prev, stage: 'error', message: '压缩失败' }))
    }
  }, [allowTextPdfRasterize, file, fileType, isWorking, jpegQuality, maxLongEdge])

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto bg-background-body">
      <div className="sticky top-0 z-10 border-b border-divider-subtle bg-background-body/95 px-8 py-5 backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <button
              type="button"
              className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-text-tertiary hover:text-text-secondary"
              onClick={() => router.push('/tools')}
            >
              <span className="i-ri-arrow-left-line size-4" />
              返回工具
            </button>
            <h1 className="text-2xl font-semibold text-text-primary">本地材料压缩 Demo</h1>
            <p className="mt-1 text-sm text-text-tertiary">
              在浏览器本地压缩 PPTX/PDF，生成可下载副本；不会上传到 Dify，也不会调用远端压缩服务。
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm font-medium text-green-700">
            <span className="i-ri-shield-check-line size-4" />
            本地处理，不上传文件
          </div>
        </div>
      </div>

      <div className="grid gap-4 p-8 xl:grid-cols-[minmax(0,560px)_minmax(0,1fr)]">
        <section className="rounded-xl border border-divider-subtle bg-components-panel-bg shadow-xs">
          <div className="border-b border-divider-subtle px-5 py-4">
            <h2 className="text-base font-semibold text-text-primary">选择文件</h2>
            <p className="mt-1 text-sm text-text-tertiary">支持 .pptx 和 .pdf；.ppt 请先另存为 .pptx。</p>
          </div>
          <div className="space-y-5 p-5">
            <label className="flex min-h-[150px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-divider-regular bg-background-section-burn p-6 text-center hover:border-components-button-primary-bg-hover hover:bg-state-base-hover">
              <span className="i-ri-upload-cloud-2-line size-8 text-text-tertiary" />
              <span className="mt-3 text-sm font-medium text-text-primary">点击选择本地文件</span>
              <span className="mt-1 text-xs text-text-tertiary">文件只会被浏览器读取，不会上传</span>
              <input
                type="file"
                accept=".pptx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                className="hidden"
                onChange={handleFileChange}
                disabled={isWorking}
              />
            </label>

            {file && (
              <div className="rounded-lg border border-divider-subtle bg-background-default p-4">
                <div className="flex items-start gap-3">
                  {fileType === 'pdf'
                    ? <span className="mt-0.5 i-ri-file-pdf-2-line size-5 text-red-500" />
                    : <span className="mt-0.5 i-ri-file-ppt-2-line size-5 text-orange-500" />}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-text-primary">{file.name}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-text-tertiary">
                      <span>{formatBytes(file.size)}</span>
                      {fileType && <span>{fileTypeLabel[fileType]}</span>}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="text-sm font-medium text-text-secondary">图片长边上限</span>
                <input
                  type="number"
                  min={800}
                  max={3000}
                  step={100}
                  value={maxLongEdge}
                  onChange={e => setMaxLongEdge(Number(e.target.value) || DEFAULT_OPTIONS.maxLongEdge)}
                  className="h-10 w-full rounded-lg border border-components-input-border-active bg-components-input-bg-normal px-3 text-sm text-text-primary outline-none focus:border-components-input-border-active"
                  disabled={isWorking}
                />
                <p className="text-xs text-text-tertiary">默认 1800px；仍太大可试 1400px。</p>
              </label>
              <label className="space-y-2">
                <span className="text-sm font-medium text-text-secondary">JPEG 质量</span>
                <input
                  type="number"
                  min={0.5}
                  max={0.95}
                  step={0.01}
                  value={jpegQuality}
                  onChange={e => setJpegQuality(Number(e.target.value) || DEFAULT_OPTIONS.jpegQuality)}
                  className="h-10 w-full rounded-lg border border-components-input-border-active bg-components-input-bg-normal px-3 text-sm text-text-primary outline-none focus:border-components-input-border-active"
                  disabled={isWorking}
                />
                <p className="text-xs text-text-tertiary">默认 0.82；仍太大可试 0.75。</p>
              </label>
            </div>

            {fileType === 'pdf' && (
              <label className="flex items-start gap-3 rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800">
                <input
                  type="checkbox"
                  checked={allowTextPdfRasterize}
                  onChange={e => setAllowTextPdfRasterize(e.target.checked)}
                  className="mt-1"
                  disabled={isWorking}
                />
                <span>
                  我确认这个 PDF 适合按扫描件处理，允许输出为图片 PDF。若原文件包含可复制文字层，压缩版可能无法复制文字。
                </span>
              </label>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={!file || isWorking}
                onClick={handleCompress}
                className={cn(
                  'inline-flex h-10 items-center gap-2 rounded-lg px-4 text-sm font-medium text-white shadow-xs',
                  !file || isWorking ? 'cursor-not-allowed bg-components-button-primary-bg-disabled' : 'bg-components-button-primary-bg hover:bg-components-button-primary-bg-hover',
                )}
              >
                {isWorking ? <span className="i-ri-loader-4-line size-4 animate-spin" /> : <span className="i-ri-download-2-line size-4" />}
                本地压缩并下载
              </button>
              {isWorking && (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="h-10 rounded-lg border border-divider-regular bg-components-button-secondary-bg px-4 text-sm font-medium text-components-button-secondary-text hover:bg-components-button-secondary-bg-hover"
                >
                  取消
                </button>
              )}
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-divider-subtle bg-components-panel-bg shadow-xs">
          <div className="border-b border-divider-subtle px-5 py-4">
            <h2 className="text-base font-semibold text-text-primary">压缩状态</h2>
            <p className="mt-1 text-sm text-text-tertiary">用于验证效果，不会改变 Dify 当前上传限制。</p>
          </div>
          <div className="space-y-5 p-5">
            <div className="rounded-lg border border-divider-subtle bg-background-default p-4">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-text-primary">{progress.message}</div>
                  <div className="mt-1 text-xs text-text-tertiary">
                    {progress.total > 0 ? `${progress.current}/${progress.total}` : '等待选择文件'}
                  </div>
                </div>
                <div className="text-sm font-semibold text-text-secondary">{progress.total > 0 ? `${progressPercent}%` : '--'}</div>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-background-section-burn">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    progress.stage === 'error' ? 'bg-red-500' : progress.stage === 'done' ? 'bg-green-500' : 'bg-components-button-primary-bg',
                  )}
                  style={{ width: `${progress.total > 0 ? progressPercent : 0}%` }}
                />
              </div>
            </div>

            {error && (
              <div className="flex gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <span className="mt-0.5 i-ri-alert-line size-5 shrink-0" />
                <div>{error}</div>
              </div>
            )}

            {report && (
              <div className="space-y-4 rounded-lg border border-green-200 bg-green-50 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-green-700">
                  <span className="i-ri-checkbox-circle-fill size-5" />
                  压缩完成：
                  {report.fileName}
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Metric label="原始大小" value={formatBytes(report.originalSize)} />
                  <Metric label="压缩后" value={formatBytes(report.outputSize)} />
                  <Metric label="压缩比例" value={`${Math.max(0, 100 - (report.outputSize / report.originalSize) * 100).toFixed(1)}%`} />
                  <Metric label="耗时" value={formatElapsed(report.elapsedMs)} />
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Metric label={report.type === 'pdf' ? '页数' : '图片数'} value={String(report.totalItems)} />
                  <Metric label="已处理" value={String(report.processedItems)} />
                  <Metric label="压缩项" value={String(report.compressedItems)} />
                </div>
                {report.warnings.length > 0 && (
                  <div className="rounded-lg bg-white/70 p-3 text-xs text-orange-700">
                    <div className="mb-1 font-medium">提示</div>
                    <ul className="list-disc space-y-1 pl-4">
                      {report.warnings.slice(0, 6).map(warning => <li key={warning}>{warning}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            )}

            <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-blue-800">
              <div className="mb-2 flex items-center gap-2 font-semibold">
                <span className="i-ri-information-line size-4" />
                如何确认没有走服务器
              </div>
              <p>
                打开浏览器 DevTools 的 Network 面板，清空记录后再选择文件并压缩。正常情况下只会有页面资源请求，不会出现 /upload、/files 或 /console/api 文件上传请求。
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

export default LocalMaterialCompressDemo
