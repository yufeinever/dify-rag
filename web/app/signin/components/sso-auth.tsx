'use client'
import type { FC } from 'react'
import { Button } from '@langgenius/dify-ui/button'
import { toast } from '@langgenius/dify-ui/toast'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Lock01 } from '@/app/components/base/icons/src/vender/solid/security'
import { useRouter, useSearchParams } from '@/next/navigation'
import { getUserOAuth2SSOUrl, getUserOIDCSSOUrl, getUserSAMLSSOUrl } from '@/service/sso'
import { SSOProtocol } from '@/types/feature'

type SSOAuthProps = {
  protocol: SSOProtocol | ''
}

const SSOAuth: FC<SSOAuthProps> = ({
  protocol,
}) => {
  const router = useRouter()
  const { t } = useTranslation()
  const searchParams = useSearchParams()
  const invite_token = decodeURIComponent(searchParams.get('invite_token') || '')

  const [isLoading, setIsLoading] = useState(false)

  const handleSSOLogin = () => {
    setIsLoading(true)
    if (protocol === SSOProtocol.SAML) {
      getUserSAMLSSOUrl(invite_token).then((res) => {
        router.push(res.url)
      }).finally(() => {
        setIsLoading(false)
      })
    }
    else if (protocol === SSOProtocol.OIDC) {
      getUserOIDCSSOUrl(invite_token).then((res) => {
        document.cookie = `user-oidc-state=${res.state};Path=/`
        router.push(res.url)
      }).finally(() => {
        setIsLoading(false)
      })
    }
    else if (protocol === SSOProtocol.OAuth2) {
      getUserOAuth2SSOUrl(invite_token).then((res) => {
        document.cookie = `user-oauth2-state=${res.state};Path=/`
        router.push(res.url)
      }).finally(() => {
        setIsLoading(false)
      })
    }
    else {
      toast.error(t('error.invalidSSOProtocol', { ns: 'login' }))
      setIsLoading(false)
    }
  }

  return (
    <Button
      tabIndex={0}
      onClick={() => { handleSSOLogin() }}
      disabled={isLoading}
      className="h-11 w-full border border-white/12 bg-[#121722] font-medium text-white shadow-inner shadow-black/10 hover:border-white/22 hover:bg-[#151b27] disabled:bg-white/5 disabled:text-white/24"
    >
      <Lock01 className="mr-2 size-5 text-[#e7bf72]" />
      <span className="truncate">{t('withSSO', { ns: 'login' }) || '使用 SSO 登录'}</span>
    </Button>
  )
}

export default SSOAuth
