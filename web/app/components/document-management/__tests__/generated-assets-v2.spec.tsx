import type { GeneratedAssetListResponse } from '@/service/generated-files'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { fetchGeneratedAssetIdentities, fetchGeneratedAssets } from '@/service/generated-files'
import GeneratedAssetsLibraryV2 from '../generated-assets-v2'

vi.mock('@/context/app-context', () => ({
  useAppContext: () => ({ isCurrentWorkspaceManager: true }),
}))

vi.mock('../original-preview', () => ({
  default: ({ generatedAssetId, onClose }: { generatedAssetId: string, onClose: () => void }) => (
    <div>
      <span>
        preview:
        {generatedAssetId}
      </span>
      <button type="button" onClick={onClose}>close-preview</button>
    </div>
  ),
}))

vi.mock('@/service/generated-files', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/service/generated-files')>()
  return {
    ...actual,
    deleteGeneratedAsset: vi.fn(),
    fetchGeneratedAssetDownloadUrl: vi.fn(),
    fetchGeneratedAssetIdentities: vi.fn(),
    fetchGeneratedAssets: vi.fn(),
    updateGeneratedAssetIdentities: vi.fn(),
  }
})

const response: GeneratedAssetListResponse = {
  data: [{
    id: 'asset-1',
    name: '方案.pptx',
    mime_type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    file_type: 'presentation',
    extension: 'pptx',
    size: 1024,
    created_at: 1_788_000_000,
    source_app_id: 'app-1',
    source_app_name: '视觉 PPT',
    source_conversation_id: null,
    source_message_id: null,
    owner_user_id: 'identity-1',
    owner_name: '飞书 · 1234',
    person_name: 'mmbadmin',
    identity_name: '飞书 · 1234',
    channel_type: 'feishu',
    identity_bound: true,
    preview_kind: 'converted_pdf',
    preview_url: '/preview',
    download_url: '/download',
    storage_type: 'tool_file',
    source_kind: 'message_file',
  }],
  page: 1,
  limit: 50,
  total: 1,
  has_more: false,
  stats: { total: 1, total_size: 1024, by_type: { presentation: 1 } },
  facets: {
    accounts: [],
    apps: [{ id: 'app-1', name: '视觉 PPT', count: 1 }],
    people: [{ id: 'account-1', name: 'mmbadmin', count: 1 }],
    channels: [{ id: 'feishu', name: '飞书', count: 1 }],
  },
}

const renderPage = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><GeneratedAssetsLibraryV2 /></QueryClientProvider>)
}

describe('GeneratedAssetsLibraryV2', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    window.history.replaceState({}, '', '/document-management')
    vi.mocked(fetchGeneratedAssets).mockResolvedValue(response)
    vi.mocked(fetchGeneratedAssetIdentities).mockResolvedValue({ identities: [], accounts: [] })
  })

  it('defaults administrators to my assets and can switch to tenant scope', async () => {
    renderPage()
    await screen.findByText('方案.pptx')
    expect(fetchGeneratedAssets).toHaveBeenCalledWith(expect.objectContaining({ scope: 'my' }))
    fireEvent.click(screen.getByRole('button', { name: '全租户' }))
    await waitFor(() => expect(fetchGeneratedAssets).toHaveBeenLastCalledWith(expect.objectContaining({ scope: 'all' })))
  })

  it('opens and closes an in-page preview without a new window', async () => {
    const openSpy = vi.spyOn(window, 'open')
    renderPage()
    fireEvent.click(await screen.findByText('方案.pptx'))
    expect(await screen.findByText('preview:asset-1')).toBeInTheDocument()
    expect(openSpy).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'close-preview' }))
    expect(screen.queryByText('preview:asset-1')).not.toBeInTheDocument()
    openSpy.mockRestore()
  })

  it('keeps people and channel filters separate', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('方案.pptx')
    await user.selectOptions(screen.getByRole('combobox', { name: '人员' }), 'account-1')
    await waitFor(() => expect(fetchGeneratedAssets).toHaveBeenLastCalledWith(expect.objectContaining({ person_ids: 'account-1' })))
    await user.selectOptions(screen.getByRole('combobox', { name: '渠道' }), 'feishu')
    await waitFor(() => expect(fetchGeneratedAssets).toHaveBeenLastCalledWith(expect.objectContaining({ person_ids: 'account-1', channel_types: 'feishu' })))
  })
})
