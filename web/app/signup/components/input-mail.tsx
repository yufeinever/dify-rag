'use client'
import type { MailRegisterResponse, MailSendResponse } from '@/service/use-common'
import { Button } from '@langgenius/dify-ui/button'
import { toast } from '@langgenius/dify-ui/toast'
import { useSuspenseQuery } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Input from '@/app/components/base/input'
import Split from '@/app/signin/split'
import { emailRegex, validPassword } from '@/config'
import { useLocale } from '@/context/i18n'
import Link from '@/next/link'
import { systemFeaturesQueryOptions } from '@/service/system-features'
import { useDirectMailRegister, useSendMail } from '@/service/use-common'
import { getBrowserTimezone } from '@/utils/timezone'

type Props = {
  onSuccess: (email: string, payload: string) => void
  onDirectSuccess?: () => void
}
export default function Form({
  onSuccess,
  onDirectSuccess,
}: Props) {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const locale = useLocale()
  const { data: systemFeatures } = useSuspenseQuery(systemFeaturesQueryOptions())
  const isDirectPasswordRegister = systemFeatures.register_mode === 'direct_password'

  const { mutateAsync: submitMail, isPending } = useSendMail()
  const { mutateAsync: directRegister, isPending: isDirectPending } = useDirectMailRegister()

  const validateEmail = useCallback(() => {
    if (!email) {
      toast.error(t('error.emailEmpty', { ns: 'login' }))
      return false
    }
    if (!emailRegex.test(email)) {
      toast.error(t('error.emailInValid', { ns: 'login' }))
      return false
    }
    return true
  }, [email, t])

  const handleSubmit = useCallback(async () => {
    if (isPending || isDirectPending)
      return

    if (!validateEmail())
      return

    if (isDirectPasswordRegister) {
      if (!password.trim()) {
        toast.error(t('error.passwordEmpty', { ns: 'login' }))
        return
      }
      if (!validPassword.test(password)) {
        toast.error(t('error.passwordInvalid', { ns: 'login' }))
        return
      }
      if (password !== confirmPassword) {
        toast.error(t('account.notEqual', { ns: 'common' }))
        return
      }
      const res = await directRegister({
        email,
        new_password: password,
        password_confirm: confirmPassword,
        language: locale,
        timezone: getBrowserTimezone(),
      })
      if ((res as MailRegisterResponse).result === 'success')
        onDirectSuccess?.()
      return
    }

    const res = await submitMail({ email, language: locale })
    if ((res as MailSendResponse).result === 'success')
      onSuccess(email, (res as MailSendResponse).data)
  }, [confirmPassword, directRegister, email, isDirectPasswordRegister, isDirectPending, isPending, locale, onDirectSuccess, onSuccess, password, submitMail, t, validateEmail])

  const submitDisabled = isDirectPasswordRegister
    ? isDirectPending || !email || !password || !confirmPassword
    : isPending || !email

  return (
    <form onSubmit={(e) => {
      e.preventDefault()
      handleSubmit()
    }}
    >
      <div className="mb-3">
        <label htmlFor="email" className="my-2 system-md-semibold text-text-secondary">
          {t('email', { ns: 'login' })}
        </label>
        <div className="mt-1">
          <Input
            value={email}
            onChange={e => setEmail(e.target.value)}
            id="email"
            type="email"
            autoComplete="email"
            placeholder={t('emailPlaceholder', { ns: 'login' }) || ''}
            tabIndex={1}
          />
        </div>
      </div>

      {isDirectPasswordRegister && (
        <>
          <div className="mb-3">
            <label htmlFor="password" className="my-2 system-md-semibold text-text-secondary">
              {t('password', { ns: 'login' })}
            </label>
            <div className="mt-1">
              <Input
                value={password}
                onChange={e => setPassword(e.target.value)}
                id="password"
                type="password"
                autoComplete="new-password"
                placeholder={t('passwordPlaceholder', { ns: 'login' }) || ''}
                tabIndex={2}
              />
            </div>
            <div className="mt-1 body-xs-regular text-text-tertiary">{t('error.passwordInvalid', { ns: 'login' })}</div>
          </div>
          <div className="mb-3">
            <label htmlFor="confirmPassword" className="my-2 system-md-semibold text-text-secondary">
              {t('confirmPassword', { ns: 'login' })}
            </label>
            <div className="mt-1">
              <Input
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                placeholder={t('confirmPasswordPlaceholder', { ns: 'login' }) || ''}
                tabIndex={3}
              />
            </div>
          </div>
        </>
      )}

      <div className="mb-2">
        <Button
          tabIndex={isDirectPasswordRegister ? 4 : 2}
          variant="primary"
          type="submit"
          disabled={submitDisabled}
          loading={isDirectPasswordRegister ? isDirectPending : isPending}
          className="w-full"
        >
          {isDirectPasswordRegister ? t('createAndSignIn', { ns: 'login' }) : t('signup.verifyMail', { ns: 'login' })}
        </Button>
      </div>
      <Split className="mt-4 mb-5" />

      <div className="text-[13px] leading-4 font-medium text-text-secondary">
        <span>{t('signup.haveAccount', { ns: 'login' })}</span>
        <Link
          className="text-text-accent"
          href="/signin"
        >
          {t('signup.signIn', { ns: 'login' })}
        </Link>
      </div>

      {!systemFeatures.branding.enabled && (
        <>
          <div className="mt-3 block w-full system-xs-regular text-text-tertiary">
            {t('tosDesc', { ns: 'login' })}
            &nbsp;
            <Link
              className="system-xs-medium text-text-secondary hover:underline"
              target="_blank"
              rel="noopener noreferrer"
              href="https://dify.ai/terms"
            >
              {t('tos', { ns: 'login' })}
            </Link>
            &nbsp;&&nbsp;
            <Link
              className="system-xs-medium text-text-secondary hover:underline"
              target="_blank"
              rel="noopener noreferrer"
              href="https://dify.ai/privacy"
            >
              {t('pp', { ns: 'login' })}
            </Link>
          </div>
        </>
      )}

    </form>
  )
}
