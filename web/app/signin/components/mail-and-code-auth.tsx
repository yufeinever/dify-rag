import type { FormEvent } from 'react'
import { Button } from '@langgenius/dify-ui/button'
import { toast } from '@langgenius/dify-ui/toast'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Input from '@/app/components/base/input'
import { COUNT_DOWN_KEY, COUNT_DOWN_TIME_MS } from '@/app/components/signin/countdown'
import { emailRegex } from '@/config'
import { useLocale } from '@/context/i18n'
import { useRouter, useSearchParams } from '@/next/navigation'
import { sendEMailLoginCode } from '@/service/common'
import { persistSigninEmail, readStoredSigninEmail } from '../utils/persistence'

const darkInputClassName = 'h-11 border-white/12 bg-[#121722] text-white placeholder:text-white/32 shadow-inner shadow-black/10 hover:border-white/22 hover:bg-[#151b27] focus:border-[#d6a54d]/70 focus:bg-[#151b27] focus:shadow-[0_0_0_3px_rgba(214,165,77,0.16)]'

type MailAndCodeAuthProps = {
  isInvite: boolean
}

export default function MailAndCodeAuth({ isInvite }: MailAndCodeAuthProps) {
  const { t } = useTranslation()
  const router = useRouter()
  const searchParams = useSearchParams()
  const emailFromLink = decodeURIComponent(searchParams.get('email') || '')
  const [email, setEmail] = useState(() => emailFromLink || readStoredSigninEmail())
  const [loading, setIsLoading] = useState(false)
  const locale = useLocale()

  const handleEmailChange = (nextEmail: string) => {
    setEmail(nextEmail)
    persistSigninEmail(nextEmail)
  }

  const handleGetEMailVerificationCode = async () => {
    try {
      if (!email) {
        toast.error(t('error.emailEmpty', { ns: 'login' }))
        return
      }

      if (!emailRegex.test(email)) {
        toast.error(t('error.emailInValid', { ns: 'login' }))
        return
      }
      setIsLoading(true)
      const ret = await sendEMailLoginCode(email, locale)
      if (ret.result === 'success') {
        localStorage.setItem(COUNT_DOWN_KEY, `${COUNT_DOWN_TIME_MS}`)
        const params = new URLSearchParams(searchParams)
        params.set('email', encodeURIComponent(email))
        params.set('token', encodeURIComponent(ret.data))
        router.push(`/signin/check-code?${params.toString()}`)
      }
    }
    catch (error) {
      console.error(error)
    }
    finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    handleGetEMailVerificationCode()
  }

  return (
    <form onSubmit={handleSubmit}>
      <input type="text" className="hidden" />
      <div className="mb-2">
        <label htmlFor="email" className="my-2 system-md-semibold text-white/72">邮箱</label>
        <div className="mt-1">
          <Input size="large" id="email" type="email" disabled={isInvite} value={email} placeholder="请输入邮箱地址" className={darkInputClassName} onChange={e => handleEmailChange(e.target.value)} />
        </div>
        <div className="mt-3">
          <Button type="submit" loading={loading} disabled={loading || !email} variant="primary" className="h-11 w-full border border-[#e7bf72]/22 bg-[#d6a54d] font-semibold text-[#15100a] shadow-[0_18px_42px_rgba(214,165,77,0.18)] hover:bg-[#e7bf72] disabled:border-white/8 disabled:bg-white/10 disabled:text-white/28 disabled:shadow-none">获取验证码</Button>
        </div>
      </div>
    </form>
  )
}
