'use client'
import { useSuspenseQuery } from '@tanstack/react-query'
import { systemFeaturesQueryOptions } from '@/service/system-features'

const Header = () => {
  const { data: systemFeatures } = useSuspenseQuery(systemFeaturesQueryOptions())

  return (
    <div className="relative z-10 flex w-full items-center justify-between px-5 py-5 sm:px-10 lg:px-14">
      <div className="flex items-center gap-3">
        {systemFeatures.branding.enabled && systemFeatures.branding.login_page_logo
          ? (
              <img
                src={systemFeatures.branding.login_page_logo}
                className="block h-8 w-auto object-contain"
                alt="logo"
              />
            )
          : (
              <div className="flex h-10 w-[92px] items-center justify-center rounded-md border border-[#d6a54d]/28 bg-white/95 p-1.5 shadow-sm">
                <img
                  src="/custom-assets/mmb-logo/logo-site.png"
                  className="h-full w-full object-contain"
                  alt="MMB"
                />
              </div>
            )}
        <div className="hidden sm:block">
          <div className="system-sm-semibold text-white/86">企业控制台</div>
          <div className="mt-0.5 text-[11px] font-medium text-white/38">Dify 权限增强版</div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className="rounded-md border border-white/10 bg-[#121722] px-3 py-1.5 text-[13px] font-medium text-white/72">
          中文
        </div>
      </div>
    </div>
  )
}

export default Header
