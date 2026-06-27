import { useQuery } from '@tanstack/react-query'
import { fetchWorkspaceUiPolicy } from '@/service/apps'

export const useUiPolicy = (enabled = true) => {
  return useQuery({
    queryKey: ['workspace', 'ui-policy'],
    queryFn: fetchWorkspaceUiPolicy,
    enabled,
    staleTime: 30000,
  })
}
