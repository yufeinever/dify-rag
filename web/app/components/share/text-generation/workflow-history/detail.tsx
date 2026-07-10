import type { InputValueTypes } from '../types'
import { Button } from '@langgenius/dify-ui/button'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Loading from '@/app/components/base/loading'
import { Markdown } from '@/app/components/base/markdown'
import { consoleQuery } from '@/service/client'

type WorkflowHistoryDetailProps = {
  appId: string
  runId: string
  onUseInputs: (inputs: Record<string, InputValueTypes>) => void
}

function getOutputString(outputs: Record<string, unknown>, key: string) {
  const value = outputs[key]
  return typeof value === 'string' ? value : ''
}

function WorkflowHistoryDetail({ appId, runId, onUseInputs }: WorkflowHistoryDetailProps) {
  const { t } = useTranslation()
  const { data: run, error, isLoading, refetch } = useQuery(
    consoleQuery.explore.installedAppWorkflowRunDetail.queryOptions({
      input: { params: { appId, runId } },
    }),
  )

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center" role="status">
        <Loading type="area" />
      </div>
    )
  }

  if (error || !run) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <span aria-hidden className="i-ri-error-warning-line size-8 text-text-destructive" />
        <p className="system-sm-regular text-text-secondary">{t('generation.history.detailError', { ns: 'share' })}</p>
        <Button onClick={() => void refetch()}>{t('generation.history.retry', { ns: 'share' })}</Button>
      </div>
    )
  }

  const characterImageUrl = run.character_image_url || getOutputString(run.outputs, 'character_image_url')
  const sceneImageUrl = run.scene_image_url || getOutputString(run.outputs, 'scene_image_url')
  const hasStructuredContent = Boolean(run.title || run.intent || run.script || run.storyboard)
  const inputs = Object.fromEntries(
    Object.entries(run.inputs).map(([key, value]) => [key, value as InputValueTypes]),
  )

  return (
    <article className="mx-auto w-full max-w-5xl pb-10">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className={`size-2 rounded-full ${run.status === 'succeeded' ? 'bg-state-success-solid' : run.status === 'running' ? 'bg-state-warning-solid' : 'bg-state-destructive-solid'}`} />
            <span className="system-xs-semibold-uppercase text-text-tertiary">
              {t(`generation.history.status.${run.status}`, { ns: 'share', defaultValue: run.status })}
            </span>
          </div>
          <h1 className="mt-2 title-2xl-semi-bold text-text-primary">
            {run.title || run.request || t('generation.history.untitled', { ns: 'share' })}
          </h1>
          {run.intent && <p className="mt-2 body-md-regular text-text-secondary">{run.intent}</p>}
        </div>
        <Button variant="secondary" onClick={() => onUseInputs(inputs)}>
          {t('generation.history.useInputs', { ns: 'share' })}
        </Button>
      </header>

      {run.video_url && (
        <section className="mb-8 rounded-2xl border border-components-panel-border bg-components-panel-bg p-4">
          <video className="aspect-video w-full rounded-xl bg-black" controls preload="metadata" src={run.video_url} />
          <div className="mt-3 flex justify-end">
            <a className="system-sm-semibold text-text-accent" href={run.video_url} download target="_blank" rel="noreferrer">
              {t('generation.history.downloadVideo', { ns: 'share' })}
            </a>
          </div>
        </section>
      )}

      {run.error && (
        <div className="mb-6 rounded-xl border border-state-destructive-border bg-state-destructive-hover p-4 body-sm-regular text-text-destructive">
          {run.error}
        </div>
      )}

      <div className="space-y-7">
        {run.script && <ContentSection title={t('generation.history.script', { ns: 'share' })} content={run.script} />}
        {run.storyboard && <ContentSection title={t('generation.history.storyboard', { ns: 'share' })} content={run.storyboard} />}
        {!hasStructuredContent && run.result && (
          <section className="prose max-w-none"><Markdown content={run.result} /></section>
        )}
        {(characterImageUrl || sceneImageUrl) && (
          <section>
            <h2 className="mb-3 title-md-semi-bold text-text-primary">{t('generation.history.images', { ns: 'share' })}</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {characterImageUrl && <ResultImage src={characterImageUrl} label={t('generation.history.characterImage', { ns: 'share' })} />}
              {sceneImageUrl && <ResultImage src={sceneImageUrl} label={t('generation.history.sceneImage', { ns: 'share' })} />}
            </div>
          </section>
        )}
        <section>
          <h2 className="mb-3 title-md-semi-bold text-text-primary">{t('generation.history.runDetails', { ns: 'share' })}</h2>
          <dl className="grid gap-3 rounded-xl border border-components-panel-border bg-components-panel-bg p-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metadata label={t('generation.history.createdAt', { ns: 'share' })} value={new Date(run.created_at * 1000).toLocaleString()} />
            <Metadata label={t('generation.history.elapsed', { ns: 'share' })} value={`${run.elapsed_time.toFixed(1)}s`} />
            <Metadata label={t('generation.history.duration', { ns: 'share' })} value={run.duration || '—'} />
            <Metadata label={t('generation.history.specification', { ns: 'share' })} value={[run.aspect_ratio, run.resolution].filter(Boolean).join(' · ') || '—'} />
          </dl>
        </section>
      </div>
    </article>
  )
}

function ContentSection({ title, content }: { title: string, content: string }) {
  return (
    <section>
      <h2 className="mb-3 title-md-semi-bold text-text-primary">{title}</h2>
      <div className="rounded-xl border border-components-panel-border bg-components-panel-bg p-5 whitespace-pre-wrap body-md-regular text-text-secondary">
        {content}
      </div>
    </section>
  )
}

function ResultImage({ src, label }: { src: string, label: string }) {
  return (
    <figure className="overflow-hidden rounded-xl border border-components-panel-border bg-components-panel-bg">
      <img src={src} alt={label} className="aspect-video w-full object-contain" />
      <figcaption className="p-3 system-sm-medium text-text-secondary">{label}</figcaption>
    </figure>
  )
}

function Metadata({ label, value }: { label: string, value: string }) {
  return (
    <div>
      <dt className="system-xs-medium text-text-tertiary">{label}</dt>
      <dd className="mt-1 system-sm-medium text-text-secondary">{value}</dd>
    </div>
  )
}

export default WorkflowHistoryDetail
