import type { WorkflowRunHistoryItem } from '@/models/explore'
import { cn } from '@langgenius/dify-ui/cn'
import { useInfiniteQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import Loading from '@/app/components/base/loading'
import { consoleQuery } from '@/service/client'

type WorkflowHistoryListProps = {
  appId: string
  selectedRunId: string | null
  onSelect: (runId: string) => void
}

const statusClassNames: Record<string, string> = {
  succeeded: 'bg-state-success-solid',
  running: 'bg-state-warning-solid',
  failed: 'bg-state-destructive-solid',
  stopped: 'bg-state-destructive-solid',
}

function formatRunTime(timestamp: number) {
  return new Intl.DateTimeFormat(undefined, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp * 1000))
}

function WorkflowHistoryList({ appId, selectedRunId, onSelect }: WorkflowHistoryListProps) {
  const { t } = useTranslation()
  const loadMoreRef = useRef<HTMLDivElement>(null)
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    refetch,
  } = useInfiniteQuery({
    ...consoleQuery.explore.installedAppWorkflowRuns.infiniteOptions({
      input: pageParam => ({
        params: { appId },
        query: {
          limit: 20,
          ...(pageParam ? { last_id: String(pageParam) } : {}),
        },
      }),
      initialPageParam: '',
      getNextPageParam: lastPage => lastPage.has_more && lastPage.last_id ? lastPage.last_id : undefined,
    }),
    enabled: !!appId,
  })
  const runs = data?.pages.flatMap(page => page.data) ?? []

  useEffect(() => {
    const target = loadMoreRef.current
    if (!target || !hasNextPage)
      return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting && !isFetchingNextPage)
        void fetchNextPage()
    })
    observer.observe(target)
    return () => observer.disconnect()
  }, [fetchNextPage, hasNextPage, isFetchingNextPage])

  if (isLoading) {
    return (
      <div className="py-10" role="status">
        <Loading type="area" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-10 text-center">
        <span aria-hidden className="i-ri-error-warning-line size-6 text-text-destructive" />
        <p className="system-sm-regular text-text-secondary">{t('generation.history.loadError', { ns: 'share' })}</p>
        <button type="button" className="system-sm-semibold text-text-accent" onClick={() => void refetch()}>
          {t('generation.history.retry', { ns: 'share' })}
        </button>
      </div>
    )
  }

  if (!runs.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-center">
        <span aria-hidden className="i-ri-movie-2-line size-8 text-text-quaternary" />
        <p className="system-sm-semibold text-text-secondary">{t('generation.history.emptyTitle', { ns: 'share' })}</p>
        <p className="system-xs-regular text-text-tertiary">{t('generation.history.emptyDescription', { ns: 'share' })}</p>
      </div>
    )
  }

  return (
    <div className="space-y-2 py-4">
      {runs.map(run => (
        <HistoryItem key={run.id} run={run} selected={run.id === selectedRunId} onSelect={onSelect} />
      ))}
      <div ref={loadMoreRef} className="flex min-h-8 items-center justify-center" role={isFetchingNextPage ? 'status' : undefined}>
        {isFetchingNextPage && <Loading type="area" />}
      </div>
    </div>
  )
}

function HistoryItem({ run, selected, onSelect }: {
  run: WorkflowRunHistoryItem
  selected: boolean
  onSelect: (runId: string) => void
}) {
  const { t } = useTranslation()
  const previewUrl = run.video_url || run.scene_image_url || run.character_image_url
  return (
    <button
      type="button"
      className={cn(
        'flex w-full gap-3 rounded-xl border p-3 text-left transition-colors',
        selected
          ? 'border-components-option-card-option-selected-border bg-state-accent-hover'
          : 'border-components-panel-border bg-components-panel-on-panel-item-bg hover:bg-state-base-hover',
      )}
      aria-pressed={selected}
      onClick={() => onSelect(run.id)}
    >
      <div className="flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-background-section-burn">
        {previewUrl
          ? <img src={previewUrl} alt="" className="size-full object-cover" />
          : <span aria-hidden className="i-ri-movie-2-line size-5 text-text-quaternary" />}
      </div>
      <div className="min-w-0 grow">
        <div className="line-clamp-2 system-sm-medium text-text-secondary">
          {run.request || t('generation.history.untitled', { ns: 'share' })}
        </div>
        <div className="mt-2 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1.5">
            <span className={cn('size-2 shrink-0 rounded-full', statusClassNames[run.status] || 'bg-state-warning-solid')} />
            <span className="truncate system-xs-medium text-text-tertiary">
              {t(`generation.history.status.${run.status}`, { ns: 'share', defaultValue: run.status })}
            </span>
          </div>
          <time className="shrink-0 system-xs-regular text-text-quaternary" dateTime={new Date(run.created_at * 1000).toISOString()}>
            {formatRunTime(run.created_at)}
          </time>
        </div>
        {run.error && <p className="mt-1 line-clamp-1 system-xs-regular text-text-destructive">{run.error}</p>}
      </div>
    </button>
  )
}

export default WorkflowHistoryList
