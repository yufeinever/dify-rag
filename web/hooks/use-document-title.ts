'use client'
import { useQuery } from '@tanstack/react-query'
import { useFavicon, useTitle } from 'ahooks'
import { useEffect } from 'react'
import { systemFeaturesQueryOptions } from '@/service/system-features'
import { defaultSystemFeatures } from '@/types/feature'
import { basePath } from '@/utils/var'

export default function useDocumentTitle(title: string) {
  const { data, isPending } = useQuery(systemFeaturesQueryOptions())
  const systemFeatures = data ?? defaultSystemFeatures
  const prefix = title ? `${title} - ` : ''
  let titleStr = ''
  let favicon = ''
  const brandingTitle = systemFeatures.branding.application_title?.trim()
  const applicationTitle = systemFeatures.branding.enabled && brandingTitle && brandingTitle.toLowerCase() !== 'dify'
    ? brandingTitle
    : 'MMB-AI'
  if (isPending === false) {
    if (systemFeatures.branding.enabled) {
      titleStr = `${prefix}${applicationTitle}`
      favicon = systemFeatures.branding.favicon
    }
    else {
      titleStr = `${prefix}${applicationTitle}`
      favicon = `${basePath}/favicon.ico`
    }
  }
  useTitle(titleStr)
  useEffect(() => {
    let apple: HTMLLinkElement | null = null
    if (systemFeatures.branding.favicon) {
      document
        .querySelectorAll(
          'link[rel=\'icon\'], link[rel=\'shortcut icon\'], link[rel=\'apple-touch-icon\'], link[rel=\'mask-icon\']',
        )
        .forEach(n => n.parentNode?.removeChild(n))

      apple = document.createElement('link')
      apple.rel = 'apple-touch-icon'
      apple.href = systemFeatures.branding.favicon
      document.head.appendChild(apple)
    }

    return () => {
      apple?.remove()
    }
  }, [systemFeatures.branding.favicon])
  useFavicon(favicon)
}
