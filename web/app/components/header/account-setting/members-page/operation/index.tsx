'use client'
import type { Member } from '@/models/common'
import { Button } from '@langgenius/dify-ui/button'
import { Dialog, DialogContent } from '@langgenius/dify-ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@langgenius/dify-ui/dropdown-menu'
import { toast } from '@langgenius/dify-ui/toast'
import { memo, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Input from '@/app/components/base/input'
import { validPassword } from '@/config'
import { useProviderContext } from '@/context/provider-context'
import { deleteMemberOrCancelInvitation, resetMemberPassword, updateMemberRole } from '@/service/common'

type IOperationProps = {
  member: Member
  operatorRole: string
  onOperate: () => void
}
const roleI18nKeyMap = {
  admin: { label: 'members.admin', tip: 'members.adminTip' },
  editor: { label: 'members.editor', tip: 'members.editorTip' },
  normal: { label: 'members.normal', tip: 'members.normalTip' },
  dataset_operator: { label: 'members.datasetOperator', tip: 'members.datasetOperatorTip' },
} as const
type OperationRoleKey = keyof typeof roleI18nKeyMap
const nonOwnerRoles = ['admin', 'editor', 'normal'] as const
const isNonOwnerRole = (role: Member['role']) => role !== 'owner'

const Operation = ({ member, operatorRole, onOperate }: IOperationProps) => {
  const { t } = useTranslation()
  const { datasetOperatorEnabled } = useProviderContext()
  const [resetPasswordOpen, setResetPasswordOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [resettingPassword, setResettingPassword] = useState(false)
  const RoleMap = {
    owner: t('members.owner', { ns: 'common' }),
    admin: t('members.admin', { ns: 'common' }),
    editor: t('members.editor', { ns: 'common' }),
    normal: t('members.normal', { ns: 'common' }),
    dataset_operator: t('members.datasetOperator', { ns: 'common' }),
  }
  const roleList = useMemo((): OperationRoleKey[] => {
    if (operatorRole === 'owner') {
      return [
        'admin',
        'editor',
        'normal',
        ...(datasetOperatorEnabled ? ['dataset_operator'] as const : []),
      ]
    }
    if (operatorRole === 'admin') {
      return [
        ...nonOwnerRoles,
        ...(datasetOperatorEnabled ? ['dataset_operator'] as const : []),
      ]
    }
    return []
  }, [operatorRole, datasetOperatorEnabled])
  const canRemoveMember = operatorRole === 'owner' || (operatorRole === 'admin' && isNonOwnerRole(member.role))
  const canResetPassword = operatorRole === 'owner' || (operatorRole === 'admin' && member.role !== 'admin' && member.role !== 'owner')
  const resetPasswordForm = () => {
    setPassword('')
    setConfirmPassword('')
  }
  const closeResetPassword = () => {
    setResetPasswordOpen(false)
    resetPasswordForm()
  }
  const handleDeleteMemberOrCancelInvitation = async () => {
    try {
      await deleteMemberOrCancelInvitation({ url: `/workspaces/current/members/${member.id}` })
      onOperate()
      toast.success(t('actionMsg.modifiedSuccessfully', { ns: 'common' }))
    }
    catch {
    }
  }
  const handleUpdateMemberRole = async (role: string) => {
    try {
      await updateMemberRole({
        url: `/workspaces/current/members/${member.id}/update-role`,
        body: { role },
      })
      onOperate()
      toast.success(t('actionMsg.modifiedSuccessfully', { ns: 'common' }))
    }
    catch {
    }
  }
  const handleResetMemberPassword = async () => {
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
    try {
      setResettingPassword(true)
      await resetMemberPassword({
        url: `/workspaces/current/members/${member.id}/password`,
        body: {
          new_password: password,
          password_confirm: confirmPassword,
        },
      })
      closeResetPassword()
      onOperate()
      toast.success(t('members.passwordResetSuccess', { ns: 'common' }))
    }
    finally {
      setResettingPassword(false)
    }
  }
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="group flex size-full cursor-pointer items-center justify-between border-none bg-transparent px-3 text-left system-sm-regular text-text-secondary hover:bg-state-base-hover data-popup-open:bg-state-base-hover"
        >
          {RoleMap[member.role] || RoleMap.normal}
          <span aria-hidden className="i-ri-arrow-down-s-line hidden size-4 shrink-0 group-hover:block group-data-popup-open:block" />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          placement="bottom-end"
          sideOffset={4}
          popupClassName="inline-flex flex-col rounded-xl p-0"
        >
          <div className="p-1">
            {roleList.map(role => (
              <DropdownMenuItem
                key={role}
                className="h-auto items-start gap-2 rounded-lg px-3 py-2"
                onClick={() => handleUpdateMemberRole(role)}
              >
                {role === member.role
                  ? <span aria-hidden className="mt-[2px] i-ri-check-line h-4 w-4 shrink-0 text-text-accent" />
                  : <span aria-hidden className="mt-[2px] h-4 w-4 shrink-0" />}
                <div>
                  <div className="system-sm-semibold whitespace-nowrap text-text-secondary">{t(roleI18nKeyMap[role].label, { ns: 'common' })}</div>
                  <div className="system-xs-regular whitespace-nowrap text-text-tertiary">{t(roleI18nKeyMap[role].tip, { ns: 'common' })}</div>
                </div>
              </DropdownMenuItem>
            ))}
          </div>
          {(canResetPassword || canRemoveMember) && (
            <>
              <DropdownMenuSeparator className="my-0" />
              <div className="p-1">
                {canResetPassword && (
                  <DropdownMenuItem
                    className="h-auto items-start gap-2 rounded-lg px-3 py-2"
                    onClick={() => setResetPasswordOpen(true)}
                  >
                    <span aria-hidden className="mt-[2px] h-4 w-4 shrink-0" />
                    <div>
                      <div className="system-sm-semibold whitespace-nowrap text-text-secondary">{t('members.resetPassword', { ns: 'common' })}</div>
                      <div className="system-xs-regular whitespace-nowrap text-text-tertiary">{t('members.resetPasswordTip', { ns: 'common' })}</div>
                    </div>
                  </DropdownMenuItem>
                )}
                {canRemoveMember && (
                  <DropdownMenuItem
                    className="h-auto items-start gap-2 rounded-lg px-3 py-2"
                    onClick={handleDeleteMemberOrCancelInvitation}
                  >
                    <span aria-hidden className="mt-[2px] h-4 w-4 shrink-0" />
                    <div>
                      <div className="system-sm-semibold whitespace-nowrap text-text-secondary">{t('members.removeFromTeam', { ns: 'common' })}</div>
                      <div className="system-xs-regular whitespace-nowrap text-text-tertiary">{t('members.removeFromTeamTip', { ns: 'common' })}</div>
                    </div>
                  </DropdownMenuItem>
                )}
              </div>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={resetPasswordOpen} onOpenChange={open => !open && closeResetPassword()}>
        <DialogContent className="w-[420px]! p-6!">
          <div className="mb-2 title-2xl-semi-bold text-text-primary">{t('members.resetPassword', { ns: 'common' })}</div>
          <div className="mb-6 body-sm-regular text-text-tertiary">{member.email}</div>
          <div className="system-sm-semibold text-text-secondary">{t('account.newPassword', { ns: 'common' })}</div>
          <Input
            className="mt-2"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
          <div className="mt-1 body-xs-regular text-text-tertiary">{t('error.passwordInvalid', { ns: 'login' })}</div>
          <div className="mt-6 system-sm-semibold text-text-secondary">{t('account.confirmPassword', { ns: 'common' })}</div>
          <Input
            className="mt-2"
            type="password"
            value={confirmPassword}
            onChange={e => setConfirmPassword(e.target.value)}
          />
          <div className="mt-8 flex justify-end gap-2">
            <Button onClick={closeResetPassword} disabled={resettingPassword}>
              {t('operation.cancel', { ns: 'common' })}
            </Button>
            <Button variant="primary" loading={resettingPassword} disabled={resettingPassword} onClick={handleResetMemberPassword}>
              {t('operation.reset', { ns: 'common' })}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
export default memo(Operation)
