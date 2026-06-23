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
              <div className="flex size-10 items-center justify-center rounded-md border border-[#d6a54d]/24 bg-[#12151d]/82 p-1 shadow-[0_10px_28px_rgba(0,0,0,0.24)] backdrop-blur">
                <img
                  src="/custom-assets/mmb-logo/logo-embedded-chat-avatar.png"
                  className="size-full object-contain drop-shadow-[0_6px_14px_rgba(0,0,0,0.24)]"
                  alt="MMB"
                />
              </div>
            )}
        <div className="hidden sm:block">
          <div className="system-sm-semibold text-white/86">AI 中台</div>
          <div className="mt-0.5 text-[11px] font-medium text-white/38">MMBAI 企业版</div>
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
