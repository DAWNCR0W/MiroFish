const debugLoggingEnabled =
  import.meta.env.DEV || import.meta.env.VITE_ENABLE_CONSOLE_LOGS === 'true'

const warningLoggingEnabled =
  debugLoggingEnabled || import.meta.env.VITE_ENABLE_CLIENT_WARNINGS === 'true'

export const debugLog = (...args) => {
  if (debugLoggingEnabled) {
    console.debug(...args)
  }
}

export const infoLog = (...args) => {
  if (debugLoggingEnabled) {
    console.info(...args)
  }
}

export const warnLog = (...args) => {
  if (warningLoggingEnabled) {
    console.warn(...args)
  }
}

export const errorLog = (...args) => {
  if (warningLoggingEnabled) {
    console.error(...args)
  }
}

export const warnDev = warnLog
export const errorDev = errorLog
