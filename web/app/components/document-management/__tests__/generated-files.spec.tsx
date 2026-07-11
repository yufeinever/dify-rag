import type { GeneratedAsset, GeneratedAssetListResponse } from '@/service/generated-files'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'
import { fetchGeneratedAssetDownloadUrl, fetchGeneratedAssets } from '@/service/generated-files'
import GeneratedAssetsLibrary, { getGeneratedAssetThumbnailUrl } from '../generated-files'

vi.mock('@/service/generated-files', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/service/generated-files')>()
  return {
    ...actual,
    deleteGeneratedAsset: vi.fn(),
    fetchGeneratedAssetDownloadUrl: vi.fn(),
    fetchGeneratedAssets: vi.fn(),
  }
})

vi.mock('@/utils/download', () => ({
  downloadUrl: vi.fn(),
}))

const createAsset = (overrides: Partial<GeneratedAsset> = {}): GeneratedAsset => ({
  id: 'asset-1',
  name: 'campaign-video.mp4',
  mime_type: 'video/mp4',
  file_type: 'video',
  extension: 'mp4',
  size: 1024,
  created_at: 1_788_000_000,
  source_app_id: 'app-1',
  source_app_name: 'Video Studio',
  source_conversation_id: null,
  source_message_id: null,
  owner_user_id: 'user-1',
  owner_name: 'Feishu User',
  preview_kind: 'native',
  preview_url: 'https://cdn.example.com/campaign-video.mp4',
  download_url: 'https://cdn.example.com/campaign-video.mp4',
  storage_type: 'remote_url',
  source_url: 'https://cdn.example.com/campaign-video.mp4',
  thumbnail_url: 'https://cdn.example.com/campaign-video.jpg',
  source_workflow_run_id: 'run-1',
  source_kind: 'workflow_video',
  asset_metadata: {},
  ...overrides,
})

const createListResponse = (assets: GeneratedAsset[]): GeneratedAssetListResponse => ({
  data: assets,
  page: 1,
  limit: 50,
  total: assets.length,
  has_more: false,
  stats: {
    total: assets.length,
    total_size: assets.reduce((total, asset) => total + asset.size, 0),
    by_type: assets.reduce<Record<string, number>>((counts, asset) => ({
      ...counts,
      [asset.file_type]: (counts[asset.file_type] ?? 0) + 1,
    }), {}),
  },
  facets: {
    accounts: [],
    apps: [],
  },
})

const renderLibrary = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <GeneratedAssetsLibrary />
    </QueryClientProvider>,
  )
}

describe('GeneratedAssetsLibrary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchGeneratedAssets).mockResolvedValue(createListResponse([createAsset()]))
  })

  describe('Video list rendering', () => {
    it('should use only the thumbnail while rendering a video row', async () => {
      const { container } = renderLibrary()

      const thumbnail = await screen.findByRole('img', { name: 'campaign-video.mp4' })

      expect(thumbnail).toHaveAttribute('src', 'https://cdn.example.com/campaign-video.jpg')
      expect(container.querySelector('video')).not.toBeInTheDocument()
      expect(container.innerHTML).not.toContain('https://cdn.example.com/campaign-video.mp4')
    })

    it('should fall back to the file icon when the thumbnail fails', async () => {
      renderLibrary()
      const thumbnail = await screen.findByRole('img', { name: 'campaign-video.mp4' })

      fireEvent.error(thumbnail)

      expect(screen.queryByRole('img', { name: 'campaign-video.mp4' })).not.toBeInTheDocument()
      expect(screen.getByText('campaign-video.mp4')).toBeInTheDocument()
    })

    it('should reject a video URL supplied as a thumbnail', () => {
      const asset = createAsset({ thumbnail_url: 'https://cdn.example.com/thumbnail.mp4' })

      expect(getGeneratedAssetThumbnailUrl(asset)).toBe('')
    })
  })

  describe('Asset actions', () => {
    it('should open the asset preview route when preview is selected', async () => {
      const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
      renderLibrary()

      fireEvent.click(await screen.findByRole('button', { name: '预览' }))

      expect(openSpy).toHaveBeenCalledWith(
        '/document-management/preview?generatedAssetId=asset-1',
        '_blank',
        'noopener,noreferrer',
      )
      openSpy.mockRestore()
    })

    it('should open a remote CDN asset in a new tab', async () => {
      const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
      vi.mocked(fetchGeneratedAssetDownloadUrl).mockResolvedValue({
        url: 'https://vidgen.x.ai/videos/campaign-video.mp4',
      })
      renderLibrary()

      fireEvent.click(await screen.findByRole('button', { name: '打开' }))

      await waitFor(() => {
        expect(openSpy).toHaveBeenCalledWith(
          'https://vidgen.x.ai/videos/campaign-video.mp4',
          '_blank',
          'noopener,noreferrer',
        )
      })
      openSpy.mockRestore()
    })
  })

  describe('Errors', () => {
    it('should show an explicit retry state when the asset request fails', async () => {
      vi.mocked(fetchGeneratedAssets).mockRejectedValue(new Error('request failed'))

      renderLibrary()

      expect(await screen.findByText('生成内容加载失败')).toBeInTheDocument()
      expect(screen.queryByText('暂无生成内容')).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument()
    })
  })

  describe('Filtering', () => {
    it('should send type, source, and inclusive date filters to the API', async () => {
      vi.mocked(fetchGeneratedAssets).mockResolvedValue(createListResponse([]))
      renderLibrary()

      fireEvent.change(screen.getByRole('combobox', { name: '内容类型' }), { target: { value: 'video' } })
      fireEvent.change(screen.getByRole('combobox', { name: '内容来源' }), { target: { value: 'workflow_video' } })
      fireEvent.change(screen.getByLabelText('开始日期'), { target: { value: '2026-07-01' } })
      fireEvent.change(screen.getByLabelText('结束日期'), { target: { value: '2026-07-11' } })

      await waitFor(() => {
        expect(fetchGeneratedAssets).toHaveBeenLastCalledWith(expect.objectContaining({
          file_type: 'video',
          source_kind: 'workflow_video',
          created_after: Math.floor(new Date('2026-07-01T00:00:00').getTime() / 1000),
          created_before: Math.floor(new Date('2026-07-12T00:00:00').getTime() / 1000),
        }))
      })
    })
  })

  describe('Pagination', () => {
    it('should request the next page instead of truncating the asset library', async () => {
      vi.mocked(fetchGeneratedAssets).mockResolvedValue({
        ...createListResponse([createAsset()]),
        total: 51,
        has_more: true,
      })
      renderLibrary()

      const nextPageButton = await screen.findByRole('button', { name: '下一页' })
      await waitFor(() => expect(nextPageButton).toBeEnabled())
      fireEvent.click(nextPageButton)

      await waitFor(() => {
        expect(fetchGeneratedAssets).toHaveBeenLastCalledWith(expect.objectContaining({
          page: 2,
          limit: 50,
        }))
      })
    })
  })
})
