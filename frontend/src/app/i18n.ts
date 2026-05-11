import { createI18n } from 'vue-i18n'
import ko from '@/locales/ko.json'
import en from '@/locales/en.json'

export type LocaleType = 'ko' | 'en'

export const LOCALE_STORAGE_KEY = 'ai-ems.locale'

const resolveInitialLocale = (): LocaleType => {
  if (typeof window === 'undefined') return 'ko'

  const savedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY)
  if (savedLocale === 'ko' || savedLocale === 'en') {
    return savedLocale
  }

  return 'ko'
}

const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: 'en',
  messages: {
    ko,
    en
  }
})

export default i18n
