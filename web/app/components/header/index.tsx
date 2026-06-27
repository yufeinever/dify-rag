'use client'
import { useSuspenseQuery } from '@tanstack/react-query'
import { useCallback } from 'react'
import DifyLogo from '@/app/components/base/logo/dify-logo'
import WorkplaceSelector from '@/app/components/header/account-dropdown/workplace-selector'
import { ACCOUNT_SETTING_TAB } from '@/app/components/header/account-setting/constants'
import { useAppContext } from '@/context/app-context'
import { useModalContext } from '@/context/modal-context'
import { useProviderContext } from '@/context/provider-context'
import { WorkspaceProvider } from '@/context/workspace-context-provider'
import useBreakpoints, { MediaType } from '@/hooks/use-breakpoints'
import { useHasAccessibleDatasets } from '@/hooks/use-has-accessible-datasets'
import { useUiPolicy } from '@/hooks/use-ui-policy'
import Link from '@/next/link'
import { systemFeaturesQueryOptions } from '@/service/system-features'
import { Plan } from '../billing/type'
import AccountDropdown from './account-dropdown'
import AppNav from './app-nav'
import DatasetNav from './dataset-nav'
import DocumentManagementNav from './document-management-nav'
import EnvNav from './env-nav'
import ExploreNav from './explore-nav'
import LicenseNav from './license-env'
import { PlanBadge } from './plan-badge'
import PluginsNav from './plugins-nav'
import ToolsNav from './tools-nav'

const navClassName = `
  flex items-center relative px-3 h-8 rounded-xl
  font-medium text-sm
  cursor-pointer
`

const Header = () => {
  const { isCurrentWorkspaceEditor, isCurrentWorkspaceDatasetOperator } = useAppContext()
  const media = useBreakpoints()
  const isMobile = media === MediaType.mobile
  const { enableBilling, plan } = useProviderContext()
  const { setShowPricingModal, setShowAccountSettingModal } = useModalContext()
  const { data: systemFeatures } = useSuspenseQuery(systemFeaturesQueryOptions())
  const { data: hasAccessibleDatasets = false } = useHasAccessibleDatasets()
  const { data: uiPolicy } = useUiPolicy()
  const showUnauthorizedResourceCards = uiPolicy?.show_unauthorized_resource_cards ?? false
  const canShowDatasetResourceNav = isCurrentWorkspaceEditor || isCurrentWorkspaceDatasetOperator || hasAccessibleDatasets
  const canShowDatasetNav = canShowDatasetResourceNav || showUnauthorizedResourceCards
  const canShowAppNav = !isCurrentWorkspaceDatasetOperator || showUnauthorizedResourceCards
  const isFreePlan = plan.type === Plan.sandbox
  const isBrandingEnabled = systemFeatures.branding.enabled
  const brandingTitle = systemFeatures.branding.application_title?.trim()
  const applicationTitle = isBrandingEnabled && brandingTitle && brandingTitle.toLowerCase() !== 'dify'
    ? brandingTitle
    : 'AI中台'
  const handlePlanClick = useCallback(() => {
    if (isFreePlan)
      setShowPricingModal()
    else
      setShowAccountSettingModal({ payload: ACCOUNT_SETTING_TAB.BILLING })
  }, [isFreePlan, setShowAccountSettingModal, setShowPricingModal])

  const renderLogo = () => (
    <h1>
      <Link href="/apps" className="flex h-8 shrink-0 items-center justify-center overflow-hidden px-0.5 indent-[-9999px] whitespace-nowrap">
        {applicationTitle}
        {systemFeatures.branding.enabled && systemFeatures.branding.workspace_logo
          ? (
              <img
                src={systemFeatures.branding.workspace_logo}
                className="block h-[22px] w-auto object-contain"
                alt="logo"
              />
            )
          : <DifyLogo />}
      </Link>
    </h1>
  )

  if (isMobile) {
    return (
      <div className="">
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center">
            {renderLogo()}
            <div className="mx-1.5 shrink-0 font-light text-divider-deep">/</div>
            <WorkspaceProvider>
              <WorkplaceSelector />
            </WorkspaceProvider>
            {enableBilling ? <PlanBadge allowHover sandboxAsUpgrade plan={plan.type} onClick={handlePlanClick} /> : <LicenseNav />}
          </div>
          <div className="flex items-center">
            {!isCurrentWorkspaceDatasetOperator && (
              <div className="mr-2">
                <ToolsNav />
              </div>
            )}
            <div className="mr-2">
              <PluginsNav />
            </div>
            <AccountDropdown />
          </div>
        </div>
        <div className="my-1 flex items-center justify-center space-x-1">
          {!isCurrentWorkspaceDatasetOperator && <ExploreNav className={navClassName} />}
          {canShowAppNav && <AppNav />}
          {canShowDatasetNav && <DatasetNav />}
          {canShowDatasetResourceNav && <DocumentManagementNav className={navClassName} />}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-[56px] items-center">
      <div className="flex min-w-0 flex-1 items-center pr-2 pl-3 min-[1280px]:pr-3">
        {renderLogo()}
        <div className="mx-1.5 shrink-0 font-light text-divider-deep">/</div>
        <WorkspaceProvider>
          <WorkplaceSelector />
        </WorkspaceProvider>
        {enableBilling ? <PlanBadge allowHover sandboxAsUpgrade plan={plan.type} onClick={handlePlanClick} /> : <LicenseNav />}
      </div>
      <div className="flex items-center space-x-2">
        {!isCurrentWorkspaceDatasetOperator && <ExploreNav className={navClassName} />}
        {canShowAppNav && <AppNav />}
        {canShowDatasetNav && <DatasetNav />}
        {canShowDatasetResourceNav && <DocumentManagementNav className={navClassName} />}
      </div>
      <div className="flex min-w-0 flex-1 items-center justify-end pr-3 pl-2 min-[1280px]:pl-3">
        <EnvNav />
        {!isCurrentWorkspaceDatasetOperator && (
          <div className="mr-2">
            <ToolsNav />
          </div>
        )}
        <div className="mr-2">
          <PluginsNav />
        </div>
        <AccountDropdown />
      </div>
    </div>
  )
}
export default Header
