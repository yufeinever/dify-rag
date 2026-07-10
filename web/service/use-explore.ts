import type { App, AppCategory, InstalledApp } from '@/models/explore'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocale } from '@/context/i18n'
import { AccessMode } from '@/models/access-control'
import { systemFeaturesQueryOptions } from '@/service/system-features'
import { consoleQuery } from './client'
import { fetchAppList, fetchBanners, fetchInstalledAppList, fetchInstalledAppMeta, fetchInstalledAppParams, getAppAccessModeByAppId, uninstallApp, updatePinStatus } from './explore'

type InstalledAppsData = {
  installed_apps: InstalledApp[]
}

type ExploreAppListData = {
  categories: AppCategory[]
  allList: App[]
}

export const useExploreAppList = () => {
  const locale = useLocale()
  const exploreAppsInput = locale
    ? { query: { language: locale } }
    : {}
  const exploreAppsLanguage = exploreAppsInput?.query?.language

  return useQuery<ExploreAppListData>({
    queryKey: [...consoleQuery.explore.apps.queryKey({ input: exploreAppsInput }), exploreAppsLanguage],
    queryFn: async () => {
      const { categories, recommended_apps } = await fetchAppList(exploreAppsLanguage)
      return {
        categories,
        allList: [...recommended_apps].sort((a, b) => a.position - b.position),
      }
    },
  })
}

export const useGetInstalledApps = () => {
  return useQuery({
    queryKey: consoleQuery.explore.installedApps.queryKey({ input: {} }),
    queryFn: () => {
      return fetchInstalledAppList()
    },
  })
}

export const useUninstallApp = () => {
  const client = useQueryClient()
  return useMutation({
    mutationKey: consoleQuery.explore.uninstallInstalledApp.mutationKey(),
    mutationFn: (appId: string) => uninstallApp(appId),
    onSuccess: () => {
      client.invalidateQueries({
        queryKey: consoleQuery.explore.installedApps.queryKey({ input: {} }),
      })
    },
  })
}

export const useUpdateAppPinStatus = () => {
  const client = useQueryClient()
  const installedAppsQueryKey = consoleQuery.explore.installedApps.queryKey({ input: {} })
  return useMutation({
    mutationKey: consoleQuery.explore.updateInstalledApp.mutationKey(),
    mutationFn: ({ appId, isPinned }: { appId: string, isPinned: boolean }) => updatePinStatus(appId, isPinned),
    onMutate: async ({ appId, isPinned }) => {
      await client.cancelQueries({ queryKey: installedAppsQueryKey })
      const previousData = client.getQueryData<InstalledAppsData>(installedAppsQueryKey)

      client.setQueryData<InstalledAppsData>(installedAppsQueryKey, (currentData) => {
        if (!currentData)
          return currentData

        const installedApps = currentData.installed_apps
          .map(app => app.id === appId ? { ...app, is_pinned: isPinned } : app)
          .sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned))

        return {
          ...currentData,
          installed_apps: installedApps,
        }
      })

      return { previousData }
    },
    onError: (_error, _variables, context) => {
      if (context?.previousData)
        client.setQueryData(installedAppsQueryKey, context.previousData)
    },
    onSettled: () => {
      client.invalidateQueries({ queryKey: installedAppsQueryKey })
    },
  })
}

export const useGetInstalledAppAccessModeByAppId = (appId: string | null) => {
  // useQuery (not useSuspenseQuery) to keep this service hook's call contract
  // unchanged from the zustand era: callers should not need a Suspense boundary.
  // First-fetch undefined is bridged via `?? false` so the inner queryKey is stable.
  const { data: systemFeatures } = useQuery(systemFeaturesQueryOptions())
  const webappAuthEnabled = systemFeatures?.webapp_auth.enabled ?? false
  const appAccessModeInput = { query: { appId: appId ?? '' } }
  const installedAppId = appAccessModeInput.query.appId

  return useQuery({
    queryKey: [
      ...consoleQuery.explore.appAccessMode.queryKey({ input: appAccessModeInput }),
      webappAuthEnabled,
      installedAppId,
    ],
    queryFn: () => {
      if (webappAuthEnabled === false) {
        return {
          accessMode: AccessMode.PUBLIC,
        }
      }
      if (!installedAppId)
        return Promise.reject(new Error('App ID is required to get access mode'))

      return getAppAccessModeByAppId(installedAppId)
    },
    enabled: !!installedAppId,
  })
}

export const useGetInstalledAppParams = (appId: string | null) => {
  const installedAppParamsInput = { params: { appId: appId ?? '' } }
  const installedAppId = installedAppParamsInput.params.appId

  return useQuery({
    queryKey: [...consoleQuery.explore.installedAppParameters.queryKey({ input: installedAppParamsInput }), installedAppId],
    queryFn: () => {
      if (!installedAppId)
        return Promise.reject(new Error('App ID is required to get app params'))
      return fetchInstalledAppParams(installedAppId)
    },
    enabled: !!installedAppId,
  })
}

export const useGetInstalledAppMeta = (appId: string | null) => {
  const installedAppMetaInput = { params: { appId: appId ?? '' } }
  const installedAppId = installedAppMetaInput.params.appId

  return useQuery({
    queryKey: [...consoleQuery.explore.installedAppMeta.queryKey({ input: installedAppMetaInput }), installedAppId],
    queryFn: () => {
      if (!installedAppId)
        return Promise.reject(new Error('App ID is required to get app meta'))
      return fetchInstalledAppMeta(installedAppId)
    },
    enabled: !!installedAppId,
  })
}

export const useGetBanners = (locale?: string) => {
  const bannersInput = locale
    ? { query: { language: locale } }
    : {}
  const bannersLanguage = bannersInput?.query?.language

  return useQuery({
    queryKey: [...consoleQuery.explore.banners.queryKey({ input: bannersInput }), bannersLanguage],
    queryFn: () => {
      return fetchBanners(bannersLanguage)
    },
  })
}
