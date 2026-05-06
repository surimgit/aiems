import { computed, ref } from 'vue'
import type { LocaleType } from '@/app/i18n'

const RESOURCE_ALIAS_COOKIE_KEY = 'ai-ems.resource-aliases'
const TEN_YEARS_IN_SECONDS = 60 * 60 * 24 * 365 * 10

type AliasByLocale = {
  ko?: string
  en?: string
}

type DraftAliasByLocale = {
  ko?: string | null
  en?: string | null
}

type ResourceAliasMap = Record<string, AliasByLocale>
type ResourceAliasDraftMap = Record<string, DraftAliasByLocale>

const aliases = ref<ResourceAliasMap>({})
const draftAliases = ref<ResourceAliasDraftMap>({})
let initialized = false

const readCookieValue = (key: string): string | null => {
  if (typeof document === 'undefined') return null

  const parts = document.cookie.split(';').map((item) => item.trim())
  const matched = parts.find((item) => item.startsWith(`${key}=`))
  if (!matched) return null

  const raw = matched.slice(key.length + 1)
  try {
    return decodeURIComponent(raw)
  } catch {
    return null
  }
}

const writeCookieValue = (key: string, value: string): void => {
  if (typeof document === 'undefined') return
  document.cookie = `${key}=${encodeURIComponent(value)}; max-age=${TEN_YEARS_IN_SECONDS}; path=/; samesite=lax`
}

const parseAliasMap = (value: string | null): ResourceAliasMap => {
  if (!value) return {}

  try {
    const parsed = JSON.parse(value) as unknown
    if (!parsed || typeof parsed !== 'object') return {}

    const normalized: ResourceAliasMap = {}
    for (const [resourceId, localeMap] of Object.entries(parsed as Record<string, unknown>)) {
      if (!localeMap || typeof localeMap !== 'object') continue
      const ko = (localeMap as Record<string, unknown>).ko
      const en = (localeMap as Record<string, unknown>).en
      normalized[resourceId] = {
        ko: typeof ko === 'string' ? ko : undefined,
        en: typeof en === 'string' ? en : undefined
      }
    }

    return normalized
  } catch {
    return {}
  }
}

const persistAliases = () => {
  writeCookieValue(RESOURCE_ALIAS_COOKIE_KEY, JSON.stringify(aliases.value))
}

const ensureInitialized = () => {
  if (initialized) return
  aliases.value = parseAliasMap(readCookieValue(RESOURCE_ALIAS_COOKIE_KEY))
  initialized = true
}

export const useResourceAlias = () => {
  ensureInitialized()

  const hasAliases = computed(() => Object.keys(aliases.value).length > 0)
  const hasPendingChanges = computed(() => Object.keys(draftAliases.value).length > 0)

  const hasDraftLocaleValue = (resourceId: string, locale: LocaleType): boolean => {
    const draft = draftAliases.value[resourceId]
    if (!draft) return false
    return Object.prototype.hasOwnProperty.call(draft, locale)
  }

  const getPersistedAlias = (resourceId: string, locale: LocaleType): string | null => {
    const localized = aliases.value[resourceId]?.[locale]?.trim()
    return localized ? localized : null
  }

  const getAlias = (resourceId: string, locale: LocaleType): string | null => {
    if (hasDraftLocaleValue(resourceId, locale)) {
      const draftValue = draftAliases.value[resourceId]?.[locale]
      if (typeof draftValue === 'string') {
        const trimmed = draftValue.trim()
        return trimmed ? trimmed : null
      }
      return null
    }

    return getPersistedAlias(resourceId, locale)
  }

  const getDisplayName = (resourceId: string, fallbackName: string, locale: LocaleType): string => {
    return getAlias(resourceId, locale) ?? fallbackName
  }

  const stageAlias = (resourceId: string, locale: LocaleType, value: string, fallbackName: string): void => {
    const trimmed = value.trim()
    const normalizedFallback = fallbackName.trim()

    const nextDraftValue: string | null = !trimmed || trimmed === normalizedFallback ? null : trimmed
    const currentDraft = draftAliases.value[resourceId] ?? {}

    draftAliases.value = {
      ...draftAliases.value,
      [resourceId]: {
        ...currentDraft,
        [locale]: nextDraftValue
      }
    }
  }

  const commitDraft = (): void => {
    const nextAliases: ResourceAliasMap = { ...aliases.value }

    for (const [resourceId, localeDraft] of Object.entries(draftAliases.value)) {
      const current = nextAliases[resourceId] ?? {}
      const updated: AliasByLocale = { ...current }

      for (const localeKey of ['ko', 'en'] as const) {
        if (!Object.prototype.hasOwnProperty.call(localeDraft, localeKey)) continue
        const draftValue = localeDraft[localeKey]

        if (typeof draftValue === 'string' && draftValue.trim().length > 0) {
          updated[localeKey] = draftValue.trim()
        } else {
          updated[localeKey] = undefined
        }
      }

      const hasKo = typeof updated.ko === 'string' && updated.ko.trim().length > 0
      const hasEn = typeof updated.en === 'string' && updated.en.trim().length > 0

      if (!hasKo && !hasEn) {
        delete nextAliases[resourceId]
      } else {
        nextAliases[resourceId] = updated
      }
    }

    aliases.value = nextAliases
    draftAliases.value = {}
    persistAliases()
  }

  return {
    aliases,
    draftAliases,
    hasAliases,
    hasPendingChanges,
    getAlias,
    getDisplayName,
    stageAlias,
    commitDraft
  }
}
