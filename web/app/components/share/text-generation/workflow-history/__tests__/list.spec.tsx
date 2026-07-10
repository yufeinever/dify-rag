import type { WorkflowRunHistoryItem } from '@/models/explore'
import { fireEvent, render, screen } from '@testing-library/react'
import WorkflowHistoryList from '../list'

const { queryState } = vi.hoisted(() => ({
  queryState: { value: null as unknown },
}))

vi.mock('@tanstack/react-query', () => ({
  useInfiniteQuery: () => queryState.value,
}))

vi.mock('@/service/client', () => ({
  consoleQuery: {
    explore: {
      installedAppWorkflowRuns: {
        infiniteOptions: () => ({}),
      },
    },
  },
}))

const createRun = (overrides: Partial<WorkflowRunHistoryItem> = {}): WorkflowRunHistoryItem => ({
  id: 'run-1',
  status: 'succeeded',
  request: 'MMB bear flies through clouds',
  created_at: 1783665600,
  finished_at: 1783665605,
  elapsed_time: 5,
  duration: '5',
  aspect_ratio: '16:9',
  resolution: '480p',
  error: null,
  video_url: 'https://example.com/video.mp4',
  character_image_url: null,
  scene_image_url: 'https://ai.meinmalzebier.shop/poster-files/files/poster-scene.png',
  ...overrides,
})

const createQueryState = (overrides: Record<string, unknown> = {}) => ({
  data: { pages: [{ data: [createRun()], has_more: false, last_id: null, limit: 20 }] },
  error: null,
  fetchNextPage: vi.fn(),
  hasNextPage: false,
  isFetchingNextPage: false,
  isLoading: false,
  refetch: vi.fn(),
  ...overrides,
})

describe('WorkflowHistoryList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryState.value = createQueryState()
  })

  it('should render a work and select it when clicked', () => {
    const onSelect = vi.fn()

    const { container } = render(<WorkflowHistoryList appId="installed-app-1" selectedRunId={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: /MMB bear flies through clouds/i }))

    expect(onSelect).toHaveBeenCalledWith('run-1')
    expect(container.querySelector('img')).toHaveAttribute('src', 'https://ai.meinmalzebier.shop/poster-files/files/poster-scene-thumb.jpg')
    expect(container.querySelector('img')).toHaveAttribute('loading', 'lazy')
  })

  it('should show the video placeholder instead of loading a full-size unsupported image', () => {
    queryState.value = createQueryState({
      data: {
        pages: [{ data: [createRun({ scene_image_url: 'https://example.com/full-size-scene.png' })] }],
      },
    })

    const { container } = render(<WorkflowHistoryList appId="installed-app-1" selectedRunId={null} onSelect={vi.fn()} />)

    expect(container.querySelector('img')).not.toBeInTheDocument()
  })

  it('should render failure status and an error summary', () => {
    queryState.value = createQueryState({
      data: {
        pages: [{ data: [createRun({ status: 'failed', error: 'Video generation failed' })] }],
      },
    })

    render(<WorkflowHistoryList appId="installed-app-1" selectedRunId="run-1" onSelect={vi.fn()} />)

    expect(screen.getByText('Video generation failed')).toBeInTheDocument()
    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true')
  })

  it('should render an empty state when there are no works', () => {
    queryState.value = createQueryState({ data: { pages: [{ data: [] }] } })

    render(<WorkflowHistoryList appId="installed-app-1" selectedRunId={null} onSelect={vi.fn()} />)

    expect(screen.getByText('share.generation.history.emptyTitle')).toBeInTheDocument()
  })

  it('should allow retrying after a list request failure', () => {
    const refetch = vi.fn()
    queryState.value = createQueryState({ error: new Error('network'), refetch })

    render(<WorkflowHistoryList appId="installed-app-1" selectedRunId={null} onSelect={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'share.generation.history.retry' }))

    expect(refetch).toHaveBeenCalledTimes(1)
  })
})
