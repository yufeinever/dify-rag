import { Button } from '@langgenius/dify-ui/button'
import { cn } from '@langgenius/dify-ui/cn'
import { API_PREFIX } from '@/config'
import { useLocale } from '@/context/i18n'
import { useSearchParams } from '@/next/navigation'
import { getPurifyHref } from '@/utils'
import { getBrowserTimezone } from '@/utils/timezone'
import style from '../page.module.css'

type SocialAuthProps = {
  disabled?: boolean
}

export default function SocialAuth(props: SocialAuthProps) {
  const searchParams = useSearchParams()
  const locale = useLocale()

  const getOAuthLink = (href: string) => {
    const url = getPurifyHref(`${API_PREFIX}${href}`)
    const params = new URLSearchParams(searchParams.toString())
    const timezone = getBrowserTimezone()
    if (timezone)
      params.set('timezone', timezone)
    params.set('language', locale)

    const query = params.toString()
    if (query)
      return `${url}?${query}`

    return url
  }
  return (
    <>
      <div className="w-full">
        <a href={getOAuthLink('/oauth/login/github')}>
          <Button
            disabled={props.disabled}
            className="h-11 w-full border border-white/12 bg-[#121722] font-medium text-white shadow-inner shadow-black/10 hover:border-white/22 hover:bg-[#151b27] disabled:bg-white/5 disabled:text-white/24"
          >
            <>
              <span className={
                cn(style.githubIcon, 'mr-2 size-5')
              }
              />
              <span className="truncate leading-normal">使用 GitHub 登录</span>
            </>
          </Button>
        </a>
      </div>
      <div className="w-full">
        <a href={getOAuthLink('/oauth/login/google')}>
          <Button
            disabled={props.disabled}
            className="h-11 w-full border border-white/12 bg-[#121722] font-medium text-white shadow-inner shadow-black/10 hover:border-white/22 hover:bg-[#151b27] disabled:bg-white/5 disabled:text-white/24"
          >
            <>
              <span className={
                cn(style.googleIcon, 'mr-2 size-5')
              }
              />
              <span className="truncate leading-normal">使用 Google 登录</span>
            </>
          </Button>
        </a>
      </div>
    </>
  )
}
