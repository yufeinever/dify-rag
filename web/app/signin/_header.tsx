'use client'

const Header = () => {
  return (
    <div className="relative z-10 flex w-full items-center justify-between px-5 py-5 sm:px-10 lg:px-14">
      <div className="hidden sm:block">
        <div className="system-sm-semibold text-white/86">AI 中台</div>
        <div className="mt-0.5 text-[11px] font-medium text-white/38">MMBAI 企业版</div>
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
