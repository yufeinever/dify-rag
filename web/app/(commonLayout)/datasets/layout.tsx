'use client'

import { useEffect } from 'react'
import Loading from '@/app/components/base/loading'
import { useAppContext } from '@/context/app-context'
import { ExternalApiPanelProvider } from '@/context/external-api-panel-context'
import { ExternalKnowledgeApiProvider } from '@/context/external-knowledge-api-context'
import { useWorkspacePermission } from '@/hooks/use-workspace-permission'
import { useRouter } from '@/next/navigation'

export default function DatasetsLayout({ children }: { children: React.ReactNode }) {
  const { isCurrentWorkspaceEditor, isCurrentWorkspaceDatasetOperator, currentWorkspace, isLoadingCurrentWorkspace } = useAppContext()
  const canWorkspace = useWorkspacePermission()
  const canViewDataset = canWorkspace('dataset.view', isCurrentWorkspaceEditor || isCurrentWorkspaceDatasetOperator)
  const router = useRouter()
  const shouldRedirect = !isLoadingCurrentWorkspace
    && currentWorkspace.id
    && !canViewDataset

  useEffect(() => {
    if (shouldRedirect)
      router.replace('/apps')
  }, [shouldRedirect, router])

  if (isLoadingCurrentWorkspace || !currentWorkspace.id)
    return <Loading type="app" />

  if (shouldRedirect) {
    return null
  }

  return (
    <ExternalKnowledgeApiProvider>
      <ExternalApiPanelProvider>
        {children}
      </ExternalApiPanelProvider>
    </ExternalKnowledgeApiProvider>
  )
}
