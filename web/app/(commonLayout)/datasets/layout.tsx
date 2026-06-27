'use client'

import { useEffect } from 'react'
import Loading from '@/app/components/base/loading'
import { useAppContext } from '@/context/app-context'
import { ExternalApiPanelProvider } from '@/context/external-api-panel-context'
import { ExternalKnowledgeApiProvider } from '@/context/external-knowledge-api-context'
import { useHasAccessibleDatasets } from '@/hooks/use-has-accessible-datasets'
import { useUiPolicy } from '@/hooks/use-ui-policy'
import { useWorkspacePermission } from '@/hooks/use-workspace-permission'
import { useRouter } from '@/next/navigation'

export default function DatasetsLayout({ children }: { children: React.ReactNode }) {
  const { isCurrentWorkspaceEditor, isCurrentWorkspaceDatasetOperator, currentWorkspace, isLoadingCurrentWorkspace } = useAppContext()
  const canWorkspace = useWorkspacePermission()
  const hasRoleDatasetView = canWorkspace('dataset.view', isCurrentWorkspaceEditor || isCurrentWorkspaceDatasetOperator)
  const { data: hasAccessibleDatasets = false, isLoading: isLoadingAccessibleDatasets } = useHasAccessibleDatasets()
  const { data: uiPolicy, isLoading: isLoadingUiPolicy } = useUiPolicy()
  const showUnauthorizedResourceCards = uiPolicy?.show_unauthorized_resource_cards ?? false
  const canViewDataset = hasRoleDatasetView || hasAccessibleDatasets || showUnauthorizedResourceCards
  const shouldWaitForDatasetAccess = (!hasRoleDatasetView && isLoadingAccessibleDatasets) || isLoadingUiPolicy
  const router = useRouter()
  const shouldRedirect = !isLoadingCurrentWorkspace
    && !shouldWaitForDatasetAccess
    && currentWorkspace.id
    && !canViewDataset

  useEffect(() => {
    if (shouldRedirect)
      router.replace('/apps')
  }, [shouldRedirect, router])

  if (isLoadingCurrentWorkspace || !currentWorkspace.id || shouldWaitForDatasetAccess)
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
