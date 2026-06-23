export type SigninAuthType = 'code' | 'password'

type AuthAvailability = {
  enableEmailCodeLogin: boolean
  enableEmailPasswordLogin: boolean
}

const SIGNIN_AUTH_TYPE_KEY = 'mmb.signin.authType'
const SIGNIN_EMAIL_KEY = 'mmb.signin.email'

const defaultAuthAvailability: AuthAvailability = {
  enableEmailCodeLogin: true,
  enableEmailPasswordLogin: true,
}

const getSessionStorage = () => {
  if (typeof window === 'undefined')
    return null

  try {
    return window.sessionStorage
  }
  catch {
    return null
  }
}

const readSessionValue = (key: string) => {
  const storage = getSessionStorage()
  if (!storage)
    return ''

  try {
    return storage.getItem(key) || ''
  }
  catch {
    return ''
  }
}

const writeSessionValue = (key: string, value: string) => {
  const storage = getSessionStorage()
  if (!storage)
    return

  try {
    if (value)
      storage.setItem(key, value)
    else
      storage.removeItem(key)
  }
  catch {
    // Ignore storage failures so private browsing or blocked storage never breaks signin.
  }
}

export const readStoredSigninAuthType = (availability: AuthAvailability = defaultAuthAvailability): SigninAuthType => {
  const storedAuthType = readSessionValue(SIGNIN_AUTH_TYPE_KEY)

  if (storedAuthType === 'password' && availability.enableEmailPasswordLogin)
    return 'password'
  if (storedAuthType === 'code' && availability.enableEmailCodeLogin)
    return 'code'

  if (availability.enableEmailPasswordLogin)
    return 'password'
  if (availability.enableEmailCodeLogin)
    return 'code'

  return 'password'
}

export const persistSigninAuthType = (authType: SigninAuthType) => {
  writeSessionValue(SIGNIN_AUTH_TYPE_KEY, authType)
}

export const readStoredSigninEmail = () => readSessionValue(SIGNIN_EMAIL_KEY)

export const persistSigninEmail = (email: string) => {
  writeSessionValue(SIGNIN_EMAIL_KEY, email.trim())
}
