import { useQuery } from '@tanstack/react-query'
import { useAppContext } from '@/context/app-context'
import { fetchDatasets } from '@/service/datasets'

export const useHasAccessibleDatasets = () => {
  const { currentWorkspace, isLoadingCurrentWorkspace } = useAppContext()

  return useQuery({
    queryKey: ['workspace', currentWorkspace.id, 'has-accessible-datasets'],
    queryFn: async () => {
      const response = await fetchDatasets({
        url: '/datasets',
        params: { page: 1, limit: 1 },
      })
      return (response.total ?? response.data.length) > 0
    },
    enabled: !!currentWorkspace.id && !isLoadingCurrentWorkspace,
    retry: false,
    staleTime: 30000,
  })
}
