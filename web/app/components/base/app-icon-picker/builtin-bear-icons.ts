export type BuiltinBearIcon = {
  id: string
  label: string
  path: string
}

const BEAR_ICON_BASE_PATH = '/custom-bear-icons'

export const BUILTIN_BEAR_ICONS: BuiltinBearIcon[] = [
  { id: 'coding', label: 'Coding', path: `${BEAR_ICON_BASE_PATH}/01-coding-bear.png` },
  { id: 'seo', label: 'Search', path: `${BEAR_ICON_BASE_PATH}/02-seo-bear.png` },
  { id: 'translation', label: 'Translation', path: `${BEAR_ICON_BASE_PATH}/03-translation-bear.png` },
  { id: 'json-repair', label: 'Tools', path: `${BEAR_ICON_BASE_PATH}/04-json-repair-bear.png` },
  { id: 'knowledge-base', label: 'Knowledge', path: `${BEAR_ICON_BASE_PATH}/05-knowledge-base-bear.png` },
  { id: 'chatbot', label: 'Chatbot', path: `${BEAR_ICON_BASE_PATH}/06-chatbot-bear.png` },
  { id: 'news-summary', label: 'News', path: `${BEAR_ICON_BASE_PATH}/07-news-summary-bear.png` },
  { id: 'customer-service', label: 'Support', path: `${BEAR_ICON_BASE_PATH}/08-customer-service-bear.png` },
  { id: 'writing', label: 'Writing', path: `${BEAR_ICON_BASE_PATH}/09-writing-bear.png` },
  { id: 'data-analysis', label: 'Analysis', path: `${BEAR_ICON_BASE_PATH}/10-data-analysis-bear.png` },
  { id: 'scheduling', label: 'Schedule', path: `${BEAR_ICON_BASE_PATH}/11-scheduling-bear.png` },
  { id: 'email', label: 'Email', path: `${BEAR_ICON_BASE_PATH}/12-email-bear.png` },
  { id: 'document-processing', label: 'Document', path: `${BEAR_ICON_BASE_PATH}/13-document-processing-bear.png` },
  { id: 'image-tool', label: 'Image', path: `${BEAR_ICON_BASE_PATH}/14-image-tool-bear.png` },
  { id: 'workflow-automation', label: 'Workflow', path: `${BEAR_ICON_BASE_PATH}/15-workflow-automation-bear.png` },
  { id: 'research-search', label: 'Research', path: `${BEAR_ICON_BASE_PATH}/16-research-search-bear.png` },
]

export const DEFAULT_BUILTIN_BEAR_ICON = BUILTIN_BEAR_ICONS[0]!
export const TAB_BUILTIN_BEAR_ICON = BUILTIN_BEAR_ICONS[5]!
