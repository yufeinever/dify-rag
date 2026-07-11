import type { GeneratedAssetPreviewConfigResponse } from '@/service/generated-files'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'
import { fetchDocumentConvertedPreviewBlob } from '@/service/datasets'
import { fetchGeneratedAssetPreviewConfig } from '@/service/generated-files'
import DocumentOriginalPreview from '../index'

let mockSearchParams = new URLSearchParams('generatedAssetId=asset-1')

vi.mock('@/next/navigation', () => ({
  useSearchParams: () => mockSearchParams,
}))

vi.mock('@/hooks/use-document-title', () => ({
  default: vi.fn(),
}))

vi.mock('@/service/datasets', () => ({
  fetchDocumentConvertedPreviewBlob: vi.fn(),
  fetchDocumentOfficePreviewConfig: vi.fn(),
}))

vi.mock('@/service/generated-files', () => ({
  fetchGeneratedAssetPreviewConfig: vi.fn(),
}))

vi.mock('@/utils/download', () => ({
  downloadUrl: vi.fn(),
}))

const createPreview = (
  overrides: Partial<GeneratedAssetPreviewConfigResponse> = {},
): GeneratedAssetPreviewConfigResponse => ({
  mode: 'remote',
  id: 'asset-1',
  name: 'campaign-video.mp4',
  mime_type: 'video/mp4',
  file_type: 'video',
  original_file_type: 'mp4',
  extension: 'mp4',
  size: 1024,
  created_at: 1_788_000_000,
  owner_user_id: 'user-1',
  owner_name: 'Feishu User',
  preview_kind: 'native',
  preview_url: 'https://cdn.example.com/campaign-video.mp4',
  download_url: 'https://cdn.example.com/campaign-video.mp4',
  storage_type: 'remote_url',
  source_url: 'https://cdn.example.com/campaign-video.mp4',
  thumbnail_url: 'https://cdn.example.com/campaign-video.jpg',
  source_kind: 'workflow_video',
  asset_metadata: {
    scene_image_url: 'https://cdn.example.com/campaign-video.jpg',
    character_image_url: 'https://cdn.example.com/campaign-character.jpg',
  },
  ...overrides,
})

const renderPreview = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <DocumentOriginalPreview />
    </QueryClientProvider>,
  )
}

describe('DocumentOriginalPreview generated assets', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams('generatedAssetId=asset-1')
    vi.mocked(fetchGeneratedAssetPreviewConfig).mockResolvedValue(createPreview())
    vi.mocked(fetchDocumentConvertedPreviewBlob).mockResolvedValue(new Blob(['pdf']))
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:converted-preview'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
  })

  describe('Remote media', () => {
    it('should load a video only on the detail page with metadata preload', async () => {
      renderPreview()

      const video = await screen.findByLabelText('campaign-video.mp4')

      expect(video).toHaveAttribute('src', 'https://cdn.example.com/campaign-video.mp4')
      expect(video).toHaveAttribute('poster', 'https://cdn.example.com/campaign-video.jpg')
      expect(video).toHaveAttribute('preload', 'metadata')
      expect(video).not.toHaveAttribute('autoplay')
      expect(await screen.findByRole('img', { name: '场景图' })).toHaveAttribute('src', 'https://cdn.example.com/campaign-video.jpg')
      expect(screen.getByRole('img', { name: '角色图' })).toHaveAttribute('src', 'https://cdn.example.com/campaign-character.jpg')
    })

    it('should render the original poster instead of its thumbnail', async () => {
      vi.mocked(fetchGeneratedAssetPreviewConfig).mockResolvedValue(createPreview({
        name: 'campaign-poster.png',
        mime_type: 'image/png',
        file_type: 'image',
        extension: 'png',
        original_file_type: 'png',
        preview_url: 'https://cdn.example.com/campaign-poster.png',
        source_url: 'https://cdn.example.com/campaign-poster.png',
        thumbnail_url: 'https://cdn.example.com/campaign-poster-thumb.jpg',
        source_kind: 'workflow_poster',
      }))

      renderPreview()

      expect(await screen.findByRole('img', { name: 'campaign-poster.png' }))
        .toHaveAttribute('src', 'https://cdn.example.com/campaign-poster.png')
    })

    it('should replace a broken remote image with the unavailable state', async () => {
      vi.mocked(fetchGeneratedAssetPreviewConfig).mockResolvedValue(createPreview({
        name: 'campaign-poster.png',
        mime_type: 'image/png',
        file_type: 'image',
        extension: 'png',
        original_file_type: 'png',
        preview_url: 'https://cdn.example.com/campaign-poster.png',
        source_url: 'https://cdn.example.com/campaign-poster.png',
        source_kind: 'workflow_poster',
      }))
      renderPreview()

      fireEvent.error(await screen.findByRole('img', { name: 'campaign-poster.png' }))

      expect(await screen.findByText('源文件暂不可用')).toBeInTheDocument()
    })
  })

  describe('Office conversion', () => {
    it('should render the converted PDF returned for a presentation', async () => {
      vi.mocked(fetchGeneratedAssetPreviewConfig).mockResolvedValue(createPreview({
        mode: 'native',
        name: 'quarterly-review.pptx',
        mime_type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        file_type: 'presentation',
        extension: 'pptx',
        original_file_type: 'pptx',
        preview_kind: 'converted_pdf',
        preview_url: '/generated-assets/asset-1/converted-preview',
        source_url: null,
        thumbnail_url: null,
      }))

      renderPreview()

      await waitFor(() => {
        expect(fetchDocumentConvertedPreviewBlob).toHaveBeenCalledWith('/generated-assets/asset-1/converted-preview')
        expect(document.querySelector('iframe[title="quarterly-review.pptx"]'))
          .toHaveAttribute('src', 'blob:converted-preview')
      })
    })
  })

  describe('Compatibility', () => {
    it('should accept the legacy generatedFileId query parameter', async () => {
      mockSearchParams = new URLSearchParams('generatedFileId=legacy-asset')

      renderPreview()

      await screen.findByLabelText('campaign-video.mp4')
      expect(fetchGeneratedAssetPreviewConfig).toHaveBeenCalledWith('legacy-asset')
    })
  })
})
