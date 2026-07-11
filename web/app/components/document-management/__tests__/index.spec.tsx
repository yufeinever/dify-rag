import type { GeneratedAssetListResponse } from '@/service/generated-files'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'
import { fetchDatasets } from '@/service/datasets'
import { fetchGeneratedAssets } from '@/service/generated-files'
import DocumentManagement from '../index'

let mockIsEditor = false
let mockIsDatasetOperator = false
let mockHasAccessibleDatasets = false

vi.mock('@/context/app-context', () => ({
  useAppContext: () => ({
    isCurrentWorkspaceEditor: mockIsEditor,
    isCurrentWorkspaceDatasetOperator: mockIsDatasetOperator,
  }),
}))

vi.mock('@/hooks/use-has-accessible-datasets', () => ({
  useHasAccessibleDatasets: () => ({ data: mockHasAccessibleDatasets }),
}))

vi.mock('@/hooks/use-document-title', () => ({
  default: vi.fn(),
}))

vi.mock('@/service/datasets', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/service/datasets')>()
  return {
    ...actual,
    fetchDatasets: vi.fn(),
    fetchDocumentDownloadUrl: vi.fn(),
    fetchDocuments: vi.fn(),
  }
})

vi.mock('@/service/generated-files', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/service/generated-files')>()
  return {
    ...actual,
    fetchGeneratedAssets: vi.fn(),
  }
})

vi.mock('@/utils/download', () => ({
  downloadUrl: vi.fn(),
}))

const emptyAssets: GeneratedAssetListResponse = {
  data: [],
  page: 1,
  limit: 100,
  total: 0,
  has_more: false,
  stats: {
    total: 0,
    total_size: 0,
    by_type: {},
  },
  facets: {
    accounts: [],
    apps: [],
  },
}

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <DocumentManagement />
    </QueryClientProvider>,
  )
}

describe('DocumentManagement access behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsEditor = false
    mockIsDatasetOperator = false
    mockHasAccessibleDatasets = false
    vi.mocked(fetchGeneratedAssets).mockResolvedValue(emptyAssets)
    vi.mocked(fetchDatasets).mockResolvedValue({
      data: [],
      has_more: false,
      limit: 100,
      page: 1,
      total: 0,
    })
  })

  it('should default to generated assets without requesting knowledge data', async () => {
    renderPage()

    expect(await screen.findByText('暂无生成内容')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '知识库文档' })).not.toBeInTheDocument()
    expect(fetchDatasets).not.toHaveBeenCalled()
  })

  it('should request knowledge data only after an authorized member selects that tab', async () => {
    mockIsEditor = true
    renderPage()

    await screen.findByText('暂无生成内容')
    expect(fetchDatasets).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: '知识库文档' }))

    await waitFor(() => expect(fetchDatasets).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('没有匹配的文档')).toBeInTheDocument()
  })
})
