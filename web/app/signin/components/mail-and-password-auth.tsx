import type { ResponseError } from '@/service/fetch'
import { Button } from '@langgenius/dify-ui/button'
import { toast } from '@langgenius/dify-ui/toast'
import { RiEyeLine, RiEyeOffLine } from '@remixicon/react'
import { noop } from 'es-toolkit/function'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { trackEvent } from '@/app/components/base/amplitude'
import Input from '@/app/components/base/input'
import { emailRegex } from '@/config'
import { useLocale } from '@/context/i18n'
import Link from '@/next/link'
import { useRouter, useSearchParams } from '@/next/navigation'
import { login } from '@/service/common'
import { setWebAppAccessToken } from '@/service/webapp-auth'
import { encryptPassword } from '@/utils/encryption'
import { persistSigninEmail, readStoredSigninEmail } from '../utils/persistence'
import { resolvePostLoginRedirect } from '../utils/post-login-redirect'

const darkInputClassName = 'h-11 border-white/12 bg-[#121722] text-white placeholder:text-white/32 shadow-inner shadow-black/10 hover:border-white/22 hover:bg-[#151b27] focus:border-[#d6a54d]/70 focus:bg-[#151b27] focus:shadow-[0_0_0_3px_rgba(214,165,77,0.16)]'

type MailAndPasswordAuthProps = {
  isInvite: boolean
  isEmailSetup: boolean
  allowRegistration: boolean
}

export default function MailAndPasswordAuth({ isInvite, isEmailSetup, allowRegistration: _allowRegistration }: MailAndPasswordAuthProps) {
  const { t } = useTranslation()
  const locale = useLocale()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [showPassword, setShowPassword] = useState(false)
  const emailFromLink = decodeURIComponent(searchParams.get('email') || '')
  const [email, setEmail] = useState(() => emailFromLink || readStoredSigninEmail())
  const [password, setPassword] = useState('')

  const [isLoading, setIsLoading] = useState(false)

  const handleEmailChange = (nextEmail: string) => {
    setEmail(nextEmail)
    persistSigninEmail(nextEmail)
  }

  const handleEmailPasswordLogin = async () => {
    if (!email) {
      toast.error(t('error.emailEmpty', { ns: 'login' }))
      return
    }
    if (!emailRegex.test(email)) {
      toast.error(t('error.emailInValid', { ns: 'login' }))
      return
    }
    if (!password?.trim()) {
      toast.error(t('error.passwordEmpty', { ns: 'login' }))
      return
    }

    try {
      setIsLoading(true)
      const loginData: Record<string, any> = {
        email,
        password: encryptPassword(password),
        language: locale,
        remember_me: true,
      }
      if (isInvite)
        loginData.invite_token = decodeURIComponent(searchParams.get('invite_token') as string)
      const res = await login({
        url: '/login',
        body: loginData,
      })
      if (res.result === 'success') {
        if (res?.data?.access_token) {
          // Track login success event
          setWebAppAccessToken(res.data.access_token)
        }
        trackEvent('user_login_success', {
          method: 'email_password',
          is_invite: isInvite,
        })

        if (isInvite) {
          router.replace(`/signin/invite-settings?${searchParams.toString()}`)
        }
        else {
          const redirectUrl = resolvePostLoginRedirect(searchParams)
          router.replace(redirectUrl || '/apps')
        }
      }
      else {
        toast.error(res.data)
      }
    }
    catch (error) {
      if ((error as ResponseError).code === 'authentication_failed') {
        toast.error(t('error.invalidEmailOrPassword', { ns: 'login' }))
      }
    }
    finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={noop}>
      <div className="mb-3">
        <label htmlFor="email" className="my-2 system-md-semibold text-white/72">
          邮箱
        </label>
        <div className="mt-1">
          <Input
            size="large"
            value={email}
            onChange={e => handleEmailChange(e.target.value)}
            disabled={isInvite}
            className={darkInputClassName}
            id="email"
            type="email"
            autoComplete="email"
            placeholder="请输入邮箱地址"
            tabIndex={1}
          />
        </div>
      </div>

      <div className="mb-3">
        <label htmlFor="password" className="my-2 flex items-center justify-between">
          <span className="system-md-semibold text-white/72">密码</span>
          <Link
            href={`/reset-password?${searchParams.toString()}`}
            className={`system-xs-regular ${isEmailSetup ? 'text-[#e7bf72] hover:text-[#f4d69a]' : 'pointer-events-none text-white/24'}`}
            tabIndex={isEmailSetup ? 0 : -1}
            aria-disabled={!isEmailSetup}
          >
            忘记密码？
          </Link>
        </label>
        <div className="relative mt-1">
          <Input
            size="large"
            id="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter')
                handleEmailPasswordLogin()
            }}
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            placeholder="请输入密码"
            className={`${darkInputClassName} pr-12`}
            tabIndex={2}
          />
          <div className="absolute inset-y-0 right-0 flex items-center">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setShowPassword(!showPassword)}
              className="text-white/54 hover:bg-white/8 hover:text-white"
            >
              {showPassword ? <RiEyeOffLine className="size-4" /> : <RiEyeLine className="size-4" />}
            </Button>
          </div>
        </div>
      </div>

      <div className="mb-2">
        <Button
          tabIndex={2}
          variant="primary"
          onClick={handleEmailPasswordLogin}
          disabled={isLoading || !email || !password}
          className="h-11 w-full border border-[#e7bf72]/22 bg-[#d6a54d] font-semibold text-[#15100a] shadow-[0_18px_42px_rgba(214,165,77,0.18)] hover:bg-[#e7bf72] disabled:border-white/8 disabled:bg-white/10 disabled:text-white/28 disabled:shadow-none"
        >
          登录
        </Button>
      </div>
    </form>
  )
}
