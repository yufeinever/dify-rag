import type { WorkflowRunHistoryDetail } from '@/models/explore'
import { fireEvent, render, screen } from '@testing-library/react'
import WorkflowHistoryDetail from '../detail'

const { queryState } = vi.hoisted(() => ({
  queryState: { value: null as unknown },
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => queryState.value,
}))

vi.mock('@/service/client', () => ({
  consoleQuery: {
    explore: {
      installedAppWorkflowRunDetail: {
        queryOptions: () => ({}),
      },
    },
  },
}))

const createDetail = (overrides: Partial<WorkflowRunHistoryDetail> = {}): WorkflowRunHistoryDetail => ({
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
  character_image_url: 'https://example.com/character.jpg',
  scene_image_url: 'https://example.com/scene.jpg',
  inputs: {
    video_request: 'MMB bear flies through clouds',
    duration: '5',
  },
  outputs: {},
  result: '# Complete result',
  script: 'A short script',
  storyboard: '1. Wide shot',
  title: 'Cloud House',
  intent: 'A warm fantasy short video.',
  ...overrides,
})

describe('WorkflowHistoryDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryState.value = {
      data: createDetail(),
      error: null,
      isLoading: false,
      refetch: vi.fn(),
    }
  })

  it('should render structured content, video preview, images, and download link', () => {
    const { container } = render(<WorkflowHistoryDetail appId="installed-app-1" runId="run-1" onUseInputs={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'Cloud House' })).toBeInTheDocument()
    expect(screen.getByText('A short script')).toBeInTheDocument()
    expect(screen.getByText('1. Wide shot')).toBeInTheDocument()
    expect(container.querySelector('video')).toHaveAttribute('src', 'https://example.com/video.mp4')
    expect(screen.getByRole('link', { name: 'share.generation.history.downloadVideo' })).toHaveAttribute('href', 'https://example.com/video.mp4')
    expect(screen.getByRole('img', { name: 'share.generation.history.characterImage' })).toBeInTheDocument()
  })

  it('should refill stored inputs without starting a run', () => {
    const onUseInputs = vi.fn()
    render(<WorkflowHistoryDetail appId="installed-app-1" runId="run-1" onUseInputs={onUseInputs} />)

    fireEvent.click(screen.getByRole('button', { name: 'share.generation.history.useInputs' }))

    expect(onUseInputs).toHaveBeenCalledWith({
      video_request: 'MMB bear flies through clouds',
      duration: '5',
    })
  })

  it('should display legacy Markdown when structured fields are missing', async () => {
    queryState.value = {
      data: createDetail({ title: null, intent: null, script: '', storyboard: '' }),
      error: null,
      isLoading: false,
      refetch: vi.fn(),
    }

    render(<WorkflowHistoryDetail appId="installed-app-1" runId="run-1" onUseInputs={vi.fn()} />)

    expect(await screen.findByText('Complete result')).toBeInTheDocument()
  })

  it('should allow retrying when detail loading fails', () => {
    const refetch = vi.fn()
    queryState.value = { data: undefined, error: new Error('network'), isLoading: false, refetch }

    render(<WorkflowHistoryDetail appId="installed-app-1" runId="run-1" onUseInputs={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'share.generation.history.retry' }))

    expect(refetch).toHaveBeenCalledTimes(1)
  })
})
