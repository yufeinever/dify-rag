import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocale } from '@/context/i18n'
import { LanguagesSupported } from '@/i18n-config/language'
import { usePipelineTemplateList } from '@/service/use-pipeline'
import TemplateCard from './template-card'

const CustomizedList = () => {
  const { t } = useTranslation()
  const locale = useLocale()
  const language = useMemo(() => {
    if (['zh-Hans', 'ja-JP'].includes(locale))
      return locale
    return LanguagesSupported[0]
  }, [locale])
  const { data: pipelineList, isLoading } = usePipelineTemplateList({ type: 'customized', language })
  const list = pipelineList?.pipeline_templates || []

  if (isLoading || list.length === 0)
    return null

  return (
    <>
      <div className="pt-2 system-sm-semibold-uppercase text-text-tertiary">{t('templates.customized', { ns: 'datasetPipeline' })}</div>
      <div className="grid grid-cols-1 gap-3 py-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {list.map((pipeline, index) => (
          <TemplateCard
            key={index}
            type="customized"
            pipeline={pipeline}
          />
        ))}
      </div>
    </>
  )
}

export default CustomizedList
