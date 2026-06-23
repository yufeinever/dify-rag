'use client'
import { cn } from '@langgenius/dify-ui/cn'
import { useSuspenseQuery } from '@tanstack/react-query'

import useDocumentTitle from '@/hooks/use-document-title'
import { systemFeaturesQueryOptions } from '@/service/system-features'
import Header from './_header'

export default function SignInLayout({ children }: any) {
  const { data: systemFeatures } = useSuspenseQuery(systemFeaturesQueryOptions())
  useDocumentTitle('登录 mmb')

  const platformMetrics = [
    { label: '权限管控', value: '五级角色' },
    { label: '企业审计', value: '全链路' },
    { label: '知识协同', value: '统一入口' },
  ]

  return (
    <>
      <div className={cn('min-h-screen w-full bg-[#07090d] text-white')}>
        <div className={cn('grid min-h-screen w-full bg-[#07090d] lg:grid-cols-[minmax(0,1.08fr)_minmax(440px,0.82fr)]')}>
          <section className="relative min-h-[430px] overflow-hidden bg-[#0b0e13] lg:min-h-screen">
            <img
              src="/custom-assets/mmb-logo/mmb-login-bears-hero.png"
              alt="mmb 品牌形象"
              className="absolute inset-0 size-full object-cover object-center saturate-[1.05]"
            />
            <div className="absolute inset-0 bg-linear-to-br from-[#05070b]/95 via-[#07100f]/70 to-[#0f1117]/42" />
            <div className="absolute inset-x-0 bottom-0 h-3/4 bg-linear-to-t from-[#07090d] via-[#07090d]/74 to-transparent" />
            <div className="absolute inset-x-0 top-0 h-24 bg-linear-to-b from-black/42 to-transparent" />
            <div className="absolute inset-y-0 right-0 w-px bg-white/10" />

            <div className="absolute top-6 left-6 flex items-center gap-3 sm:top-9 sm:left-10 lg:left-14">
              <div className="flex size-12 items-center justify-center rounded-md border border-[#d6a54d]/28 bg-[#12151d]/82 p-1.5 shadow-[0_12px_36px_rgba(0,0,0,0.28)] backdrop-blur">
                <img
                  src="/custom-assets/mmb-logo/logo-embedded-chat-avatar.png"
                  className="size-full object-contain drop-shadow-[0_8px_18px_rgba(0,0,0,0.26)]"
                  alt="MMB"
                />
              </div>
              <div className="hidden text-[13px] font-medium text-white/70 sm:block">广场啤酒企业 AI 平台</div>
            </div>

            <div className="absolute right-6 bottom-6 hidden w-[270px] rounded-lg border border-white/10 bg-[#10141a]/76 p-4 shadow-[0_24px_70px_rgba(0,0,0,0.32)] backdrop-blur lg:block">
              <div className="mb-3 flex items-center justify-between border-b border-white/10 pb-3">
                <div>
                  <div className="text-[12px] font-medium text-white/46">当前安全策略</div>
                  <div className="mt-1 text-[15px] font-semibold text-white">企业方案 B+</div>
                </div>
                <div className="h-2 w-2 rounded-full bg-[#64d98a] shadow-[0_0_18px_rgba(100,217,138,0.65)]" />
              </div>
              <div className="space-y-2 text-[12px] text-white/58">
                <div className="flex items-center justify-between">
                  <span>成员管理</span>
                  <span className="text-[#e7bf72]">管理员可见</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>知识库操作</span>
                  <span className="text-[#e7bf72]">角色隔离</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>工作区配置</span>
                  <span className="text-[#e7bf72]">所有者控制</span>
                </div>
              </div>
            </div>

            <div className="absolute right-6 bottom-6 left-6 max-w-[610px] text-white sm:bottom-10 sm:left-10 lg:bottom-14 lg:left-14">
              <div className="mb-5 inline-flex h-9 items-center rounded-md border border-[#d6a54d]/28 bg-[#12151d]/82 px-3 text-[13px] leading-none font-semibold text-[#e7bf72] backdrop-blur">
                企业级统一登录
              </div>
              <h1 className="max-w-[570px] text-[32px] leading-tight font-semibold text-white sm:text-[42px]">
                广场啤酒业务智能管理中枢
              </h1>
              <p className="mt-4 max-w-[500px] text-[15px] leading-6 text-white/70">
                面向门店、运营、活动、知识库与团队协作的统一入口，登录后进入真实 Dify 工作台，按企业角色控制可访问能力。
              </p>
              <div className="mt-8 grid max-w-[560px] grid-cols-3 border-y border-white/10 py-4 text-white/72">
                {platformMetrics.map((metric, index) => (
                  <div key={metric.label} className={cn(index === 1 && 'border-x border-white/10 px-5', index === 2 && 'pl-5')}>
                    <div className="text-[17px] font-semibold text-white">{metric.value}</div>
                    <div className="mt-1 text-[12px]">{metric.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="relative flex min-h-[calc(100vh-430px)] flex-col overflow-hidden bg-[#090c12] lg:min-h-screen">
            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,#111722_0%,#0b0f16_42%,#07090d_100%)]" />
            <div className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-linear-to-b from-[#d6a54d]/10 to-transparent" />
            <Header />
            <div className={cn('relative flex w-full grow flex-col items-center justify-center px-5 py-8 sm:px-10 lg:px-14')}>
              <div className="flex w-full max-w-[444px] flex-col rounded-lg border border-white/10 bg-[#0f141d]/88 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.38)] backdrop-blur sm:p-8">
                {children}
              </div>
            </div>
            {systemFeatures.branding.enabled === false && (
              <div className="relative px-8 pb-6 text-center system-xs-regular text-white/38">
                ©
                {' '}
                {new Date().getFullYear()}
                {' '}
                mmb. 保留所有权利。
              </div>
            )}
          </section>
        </div>
      </div>
    </>
  )
}
