import type { SigninAuthType } from './utils/persistence'
import { cn } from '@langgenius/dify-ui/cn'
import { toast } from '@langgenius/dify-ui/toast'
import { RiContractLine, RiDoorLockLine, RiErrorWarningFill } from '@remixicon/react'
import { useQuery, useSuspenseQuery } from '@tanstack/react-query'
import * as React from 'react'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { IS_CE_EDITION } from '@/config'
import Link from '@/next/link'
import { useRouter, useSearchParams } from '@/next/navigation'
import { invitationCheck } from '@/service/common'
import { systemFeaturesQueryOptions } from '@/service/system-features'
import { isLegacyBase401, userProfileQueryOptions } from '@/service/use-common'
import { LicenseStatus } from '@/types/feature'
import Loading from '../components/base/loading'
import MailAndCodeAuth from './components/mail-and-code-auth'
import MailAndPasswordAuth from './components/mail-and-password-auth'
import SocialAuth from './components/social-auth'
import SSOAuth from './components/sso-auth'
import Split from './split'
import { persistSigninAuthType, readStoredSigninAuthType } from './utils/persistence'
import { resolvePostLoginRedirect } from './utils/post-login-redirect'

const NormalForm = () => {
  const { t } = useTranslation()
  const router = useRouter()
  const searchParams = useSearchParams()
  // Login probe: 401 stays as `error` (legitimate "not logged in" state on /signin),
  // other errors throw to error.tsx. jumpTo same-pathname guard in service/base.ts
  // prevents the redirect loop on 401.
  const { isPending: isCheckLoading, data: userResp, error: probeError } = useQuery({
    ...userProfileQueryOptions(),
    throwOnError: err => !isLegacyBase401(err),
  })
  const isLoggedIn = !!userResp && !probeError
  const message = decodeURIComponent(searchParams.get('message') || '')
  const invite_token = decodeURIComponent(searchParams.get('invite_token') || '')
  const [isInitCheckLoading, setInitCheckLoading] = useState(true)
  const [isRedirecting, setIsRedirecting] = useState(false)
  const isLoading = isCheckLoading || isInitCheckLoading || isRedirecting
  const { data: systemFeatures } = useSuspenseQuery(systemFeaturesQueryOptions())
  const [authType, updateAuthType] = useState<SigninAuthType>(() => readStoredSigninAuthType())
  const [showORLine, setShowORLine] = useState(false)
  const [allMethodsAreDisabled, setAllMethodsAreDisabled] = useState(false)
  const [workspaceName, setWorkSpaceName] = useState('')

  const isInviteLink = Boolean(invite_token && invite_token !== 'null')

  const init = useCallback(async () => {
    try {
      if (isLoggedIn) {
        setIsRedirecting(true)
        const redirectUrl = resolvePostLoginRedirect(searchParams)
        router.replace(redirectUrl || '/apps')
        return
      }

      if (message) {
        toast.error(message)
      }
      setAllMethodsAreDisabled(!systemFeatures.enable_social_oauth_login && !systemFeatures.enable_email_code_login && !systemFeatures.enable_email_password_login && !systemFeatures.sso_enforced_for_signin)
      setShowORLine((systemFeatures.enable_social_oauth_login || systemFeatures.sso_enforced_for_signin) && (systemFeatures.enable_email_code_login || systemFeatures.enable_email_password_login))
      updateAuthType(readStoredSigninAuthType({
        enableEmailCodeLogin: systemFeatures.enable_email_code_login,
        enableEmailPasswordLogin: systemFeatures.enable_email_password_login,
      }))
      if (isInviteLink) {
        const checkRes = await invitationCheck({
          url: '/activate/check',
          params: {
            token: invite_token,
          },
        })
        setWorkSpaceName(checkRes?.data?.workspace_name || '')
      }
    }
    catch (error) {
      console.error(error)
      setAllMethodsAreDisabled(true)
    }
    finally { setInitCheckLoading(false) }
  }, [isLoggedIn, message, router, invite_token, isInviteLink, systemFeatures])
  useEffect(() => {
    init()
  }, [init])
  const handleAuthTypeChange = useCallback((nextAuthType: SigninAuthType) => {
    persistSigninAuthType(nextAuthType)
    updateAuthType(nextAuthType)
  }, [])
  if (isLoading) {
    return (
      <div className={
        cn(
          'flex w-full grow flex-col items-center justify-center',
          'px-6',
          'md:px-[108px]',
        )
      }
      >
        <Loading type="area" />
      </div>
    )
  }
  if (systemFeatures.license?.status === LicenseStatus.LOST) {
    return (
      <div className="mx-auto mt-8 w-full">
        <div className="relative">
          <div className="rounded-lg bg-linear-to-r from-workflow-workflow-progress-bg-1 to-workflow-workflow-progress-bg-2 p-4">
            <div className="shadows-shadow-lg relative mb-2 flex size-10 items-center justify-center rounded-xl bg-components-card-bg shadow">
              <RiContractLine className="size-5" />
              <RiErrorWarningFill className="absolute -top-1 -right-1 size-4 text-text-warning-secondary" />
            </div>
            <p className="system-sm-medium text-text-primary">{t('licenseLost', { ns: 'login' })}</p>
            <p className="mt-1 system-xs-regular text-text-tertiary">{t('licenseLostTip', { ns: 'login' })}</p>
          </div>
        </div>
      </div>
    )
  }
  if (systemFeatures.license?.status === LicenseStatus.EXPIRED) {
    return (
      <div className="mx-auto mt-8 w-full">
        <div className="relative">
          <div className="rounded-lg bg-linear-to-r from-workflow-workflow-progress-bg-1 to-workflow-workflow-progress-bg-2 p-4">
            <div className="shadows-shadow-lg relative mb-2 flex size-10 items-center justify-center rounded-xl bg-components-card-bg shadow">
              <RiContractLine className="size-5" />
              <RiErrorWarningFill className="absolute -top-1 -right-1 size-4 text-text-warning-secondary" />
            </div>
            <p className="system-sm-medium text-text-primary">{t('licenseExpired', { ns: 'login' })}</p>
            <p className="mt-1 system-xs-regular text-text-tertiary">{t('licenseExpiredTip', { ns: 'login' })}</p>
          </div>
        </div>
      </div>
    )
  }
  if (systemFeatures.license?.status === LicenseStatus.INACTIVE) {
    return (
      <div className="mx-auto mt-8 w-full">
        <div className="relative">
          <div className="rounded-lg bg-linear-to-r from-workflow-workflow-progress-bg-1 to-workflow-workflow-progress-bg-2 p-4">
            <div className="shadows-shadow-lg relative mb-2 flex size-10 items-center justify-center rounded-xl bg-components-card-bg shadow">
              <RiContractLine className="size-5" />
              <RiErrorWarningFill className="absolute -top-1 -right-1 size-4 text-text-warning-secondary" />
            </div>
            <p className="system-sm-medium text-text-primary">{t('licenseInactive', { ns: 'login' })}</p>
            <p className="mt-1 system-xs-regular text-text-tertiary">{t('licenseInactiveTip', { ns: 'login' })}</p>
          </div>
        </div>
      </div>
    )
  }

  const securityHighlights = [
    '企业角色校验',
    '工作区级隔离',
    '登录后审计追踪',
  ]

  return (
    <>
      <div className="mx-auto w-full">
        {isInviteLink
          ? (
              <div className="mx-auto w-full">
                <div className="mb-4 inline-flex h-8 items-center rounded-md border border-[#d6a54d]/24 bg-[#161a22] px-3 text-[12px] font-semibold text-[#e7bf72]">
                  企业邀请登录
                </div>
                <h2 className="title-4xl-semi-bold text-white">
                  加入
                  {workspaceName}
                </h2>
                {!systemFeatures.branding.enabled && (
                  <p className="mt-2 body-md-regular text-white/58">
                    你正在加入
                    {workspaceName}
                    ，请登录或完成验证后继续。
                  </p>
                )}
              </div>
            )
          : (
              <div className="mx-auto w-full">
                <div className="mb-4 flex items-center justify-between rounded-lg border border-white/10 bg-[#121722]/72 px-3 py-2">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-md border border-[#d6a54d]/24 bg-[#171b24]/88 p-1 shadow-[0_10px_24px_rgba(0,0,0,0.22)]">
                      <img
                        src="/custom-assets/mmb-logo/logo-embedded-chat-avatar.png"
                        className="size-full object-contain drop-shadow-[0_5px_12px_rgba(0,0,0,0.22)]"
                        alt="MMB"
                      />
                    </div>
                    <div className="min-w-0">
                      <div className="text-[12px] font-medium text-white/42">访问入口</div>
                      <div className="mt-0.5 truncate text-[13px] font-semibold text-white">mmb 企业身份中心</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-[12px] font-medium text-[#64d98a]">
                    <span className="h-2 w-2 rounded-full bg-[#64d98a]" />
                    安全在线
                  </div>
                </div>
                <p className="mb-3 system-sm-medium text-[#e7bf72]">企业安全登录</p>
                <h2 className="title-4xl-semi-bold text-white">登录 mmb</h2>
                <p className="mt-3 body-md-regular text-white/58">进入 Dify 工作台，管理知识库、工作流、应用与团队权限。</p>
                <div className="mt-5 grid grid-cols-3 gap-2">
                  {securityHighlights.map(item => (
                    <div key={item} className="min-h-12 rounded-md border border-white/10 bg-[#10151d] px-2 py-2 text-[12px] leading-4 text-white/64">
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            )}
        <div className="relative">
          <div className="mt-6 flex flex-col gap-3">
            {systemFeatures.enable_social_oauth_login && <SocialAuth />}
            {systemFeatures.sso_enforced_for_signin && (
              <div className="w-full">
                <SSOAuth protocol={systemFeatures.sso_enforced_for_signin_protocol} />
              </div>
            )}
          </div>

          {showORLine && (
            <div className="relative mt-6">
              <div className="flex items-center">
                <div className="h-px flex-1 bg-linear-to-r from-transparent to-white/14"></div>
                <span className="px-3 system-xs-medium-uppercase text-white/42">或</span>
                <div className="h-px flex-1 bg-linear-to-l from-transparent to-white/14"></div>
              </div>
            </div>
          )}
          {
            (systemFeatures.enable_email_code_login || systemFeatures.enable_email_password_login) && (
              <>
                {systemFeatures.enable_email_code_login && authType === 'code' && (
                  <>
                    <MailAndCodeAuth isInvite={isInviteLink} />
                    {systemFeatures.enable_email_password_login && (
                      <div className="cursor-pointer py-1 text-center" onClick={() => { handleAuthTypeChange('password') }}>
                        <span className="system-xs-medium text-[#e7bf72] hover:text-[#f4d69a]">使用密码登录</span>
                      </div>
                    )}
                  </>
                )}
                {systemFeatures.enable_email_password_login && authType === 'password' && (
                  <>
                    <MailAndPasswordAuth isInvite={isInviteLink} isEmailSetup={systemFeatures.is_email_setup} allowRegistration={systemFeatures.is_allow_register} />
                    {systemFeatures.enable_email_code_login && (
                      <div className="cursor-pointer py-1 text-center" onClick={() => { handleAuthTypeChange('code') }}>
                        <span className="system-xs-medium text-[#e7bf72] hover:text-[#f4d69a]">使用验证码登录</span>
                      </div>
                    )}
                  </>
                )}
                <Split className="mt-4 mb-5" />
              </>
            )
          }

          {systemFeatures.is_allow_register && authType === 'password' && (
            <div className="mb-3 text-[13px] leading-4 font-medium text-white/58">
              <span>还没有账号？</span>
              <Link
                className="ml-1 text-[#e7bf72] hover:text-[#f4d69a]"
                href="/signup"
              >
                立即注册
              </Link>
            </div>
          )}
          {allMethodsAreDisabled && (
            <>
              <div className="rounded-lg bg-linear-to-r from-workflow-workflow-progress-bg-1 to-workflow-workflow-progress-bg-2 p-4">
                <div className="shadows-shadow-lg mb-2 flex size-10 items-center justify-center rounded-xl bg-components-card-bg shadow">
                  <RiDoorLockLine className="size-5" />
                </div>
                <p className="system-sm-medium text-white">当前没有可用的登录方式</p>
                <p className="mt-1 system-xs-regular text-white/58">请联系管理员开启邮箱、验证码、SSO 或社交登录。</p>
              </div>
              <div className="relative my-2 py-2">
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-px w-full bg-linear-to-r from-transparent via-white/14 to-transparent"></div>
                </div>
              </div>
            </>
          )}
          {!systemFeatures.branding.enabled && (
            <>
              <div className="mt-2 rounded-md border border-white/8 bg-white/[0.03] px-3 py-2 system-xs-regular text-white/42">
                登录即表示你同意
              &nbsp;
                <Link
                  className="system-xs-medium text-white/64 hover:text-white hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                  href="https://dify.ai/terms"
                >
                  服务条款
                </Link>
              &nbsp;和&nbsp;
                <Link
                  className="system-xs-medium text-white/64 hover:text-white hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                  href="https://dify.ai/privacy"
                >
                  隐私政策
                </Link>
              </div>
              {IS_CE_EDITION && (
                <div className="w-hull mt-2 block system-xs-regular text-white/42">
                  首次部署？
              &nbsp;
                  <Link
                    className="system-xs-medium text-white/64 hover:text-white hover:underline"
                    href="/install"
                  >
                    设置管理员账号
                  </Link>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}

export default NormalForm
