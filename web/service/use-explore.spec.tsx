import type { ReactNode } from 'react'
import type { InstalledApp } from '@/models/explore'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppModeEnum } from '@/types/app'
import { consoleQuery } from './client'
import { updatePinStatus } from './explore'
import { useUpdateAppPinStatus } from './use-explore'

vi.mock('./explore', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./explore')>()
  return {
    ...actual,
    updatePinStatus: vi.fn(),
  }
})

const createInstalledApp = (id: string, isPinned: boolean): InstalledApp => ({
  id,
  is_pinned: isPinned,
  uninstallable: false,
  app: {
    id: `source-${id}`,
    mode: AppModeEnum.CHAT,
    icon_type: 'emoji',
    icon: 'A',
    icon_background: '#fff',
    icon_url: '',
    name: id,
    description: '',
    use_icon_as_answer_icon: false,
  },
})

describe('useUpdateAppPinStatus', () => {
  const queryKey = consoleQuery.explore.installedApps.queryKey({ input: {} })
  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    queryClient.setQueryData(queryKey, {
      installed_apps: [
        createInstalledApp('pinned', true),
        createInstalledApp('regular', false),
      ],
    })
  })

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  it('optimistically pins and moves an app before the request finishes', async () => {
    queryClient.setQueryData(queryKey, {
      installed_apps: [
        createInstalledApp('other', false),
        createInstalledApp('regular', false),
      ],
    })
    let resolveRequest: (() => void) | undefined
    vi.mocked(updatePinStatus).mockReturnValue(new Promise((resolve) => {
      resolveRequest = () => resolve({ result: 'success', message: 'ok' })
    }))
    const { result } = renderHook(() => useUpdateAppPinStatus(), { wrapper })

    act(() => result.current.mutate({ appId: 'regular', isPinned: true }))

    await waitFor(() => {
      const data = queryClient.getQueryData<{ installed_apps: InstalledApp[] }>(queryKey)
      expect(data?.installed_apps.map(app => app.id)).toEqual(['regular', 'other'])
      expect(data?.installed_apps.map(app => app.is_pinned)).toEqual([true, false])
    })

    resolveRequest?.()
  })

  it('rolls the optimistic update back when the request fails', async () => {
    vi.mocked(updatePinStatus).mockRejectedValue(new Error('request failed'))
    const { result } = renderHook(() => useUpdateAppPinStatus(), { wrapper })

    await act(async () => {
      await expect(result.current.mutateAsync({ appId: 'regular', isPinned: true })).rejects.toThrow('request failed')
    })

    const data = queryClient.getQueryData<{ installed_apps: InstalledApp[] }>(queryKey)
    expect(data?.installed_apps.map(app => [app.id, app.is_pinned])).toEqual([
      ['pinned', true],
      ['regular', false],
    ])
  })
})
