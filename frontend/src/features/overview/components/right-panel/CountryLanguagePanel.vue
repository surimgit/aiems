<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LOCALE_STORAGE_KEY, type LocaleType } from '@/app/i18n'

type CountryItem = {
  code: string
  nameKo: string
  nameEn: string
  flag: string
}

const countries: CountryItem[] = [
  { code: 'KR', nameKo: '대한민국', nameEn: 'Korea', flag: '🇰🇷' },
  { code: 'US', nameKo: '미국', nameEn: 'United States', flag: '🇺🇸' },
  { code: 'JP', nameKo: '일본', nameEn: 'Japan', flag: '🇯🇵' },
  { code: 'CN', nameKo: '중국', nameEn: 'China', flag: '🇨🇳' },
  { code: 'DE', nameKo: '독일', nameEn: 'Germany', flag: '🇩🇪' },
  { code: 'GB', nameKo: '영국', nameEn: 'United Kingdom', flag: '🇬🇧' },
  { code: 'FR', nameKo: '프랑스', nameEn: 'France', flag: '🇫🇷' },
  { code: 'CA', nameKo: '캐나다', nameEn: 'Canada', flag: '🇨🇦' },
  { code: 'AU', nameKo: '호주', nameEn: 'Australia', flag: '🇦🇺' },
  { code: 'IN', nameKo: '인도', nameEn: 'India', flag: '🇮🇳' },
  { code: 'BR', nameKo: '브라질', nameEn: 'Brazil', flag: '🇧🇷' },
  { code: 'RU', nameKo: '러시아', nameEn: 'Russia', flag: '🇷🇺' },
  { code: 'IT', nameKo: '이탈리아', nameEn: 'Italy', flag: '🇮🇹' },
  { code: 'ES', nameKo: '스페인', nameEn: 'Spain', flag: '🇪🇸' },
  { code: 'NL', nameKo: '네덜란드', nameEn: 'Netherlands', flag: '🇳🇱' },
  { code: 'SE', nameKo: '스웨덴', nameEn: 'Sweden', flag: '🇸🇪' },
  { code: 'SG', nameKo: '싱가포르', nameEn: 'Singapore', flag: '🇸🇬' },
  { code: 'VN', nameKo: '베트남', nameEn: 'Vietnam', flag: '🇻🇳' },
  { code: 'ID', nameKo: '인도네시아', nameEn: 'Indonesia', flag: '🇮🇩' },
  { code: 'TH', nameKo: '태국', nameEn: 'Thailand', flag: '🇹🇭' },
  { code: 'MY', nameKo: '말레이시아', nameEn: 'Malaysia', flag: '🇲🇾' },
  { code: 'PH', nameKo: '필리핀', nameEn: 'Philippines', flag: '🇵🇭' },
  { code: 'AE', nameKo: '아랍에미리트', nameEn: 'United Arab Emirates', flag: '🇦🇪' },
  { code: 'SA', nameKo: '사우디아라비아', nameEn: 'Saudi Arabia', flag: '🇸🇦' },
  { code: 'MX', nameKo: '멕시코', nameEn: 'Mexico', flag: '🇲🇽' },
  { code: 'TR', nameKo: '튀르키예', nameEn: 'Türkiye', flag: '🇹🇷' },
  { code: 'ZA', nameKo: '남아프리카공화국', nameEn: 'South Africa', flag: '🇿🇦' },
  { code: 'NZ', nameKo: '뉴질랜드', nameEn: 'New Zealand', flag: '🇳🇿' },
  { code: 'CH', nameKo: '스위스', nameEn: 'Switzerland', flag: '🇨🇭' }
]

const query = ref('')
const selectedCountry = ref('KR')
const { t, locale } = useI18n()

const selectedLang = ref<'KO' | 'EN'>(locale.value === 'en' ? 'EN' : 'KO')
const appliedMessage = ref('')

const displayCountryName = (country: CountryItem): string => (locale.value === 'en' ? country.nameEn : country.nameKo)

const koLabel = computed(() => (locale.value === 'en' ? 'KR' : '한국어'))
const enLabel = computed(() => (locale.value === 'en' ? 'EN' : '영어'))

const filteredCountries = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return countries
  return countries.filter((item) =>
    item.nameKo.toLowerCase().includes(keyword) || item.nameEn.toLowerCase().includes(keyword) || item.code.toLowerCase().includes(keyword)
  )
})

const applySetting = () => {
  const country = countries.find((item) => item.code === selectedCountry.value)
  const nextLocale = selectedLang.value.toLowerCase() as LocaleType
  locale.value = nextLocale
  window.localStorage.setItem(LOCALE_STORAGE_KEY, nextLocale)
  appliedMessage.value = `${t('countryPanel.applied')}: ${country ? displayCountryName(country) : selectedCountry.value} / ${selectedLang.value}`
}
</script>

<template>
  <div class="panel-content">
    <div class="search-wrap">
      <input v-model="query" type="text" class="search-input" :placeholder="t('countryPanel.searchPlaceholder')" />
    </div>

    <div class="country-grid">
      <button
        v-for="country in filteredCountries"
        :key="country.code"
        type="button"
        class="country-btn"
        :class="{ active: selectedCountry === country.code }"
        @click="selectedCountry = country.code"
      >
        <span class="flag">{{ country.flag }}</span>
        <span class="name">{{ displayCountryName(country) }}</span>
      </button>
    </div>

    <div class="lang-wrap">
      <p class="section-title">{{ t('countryPanel.languageTitle') }}</p>
      <div class="lang-grid">
        <button type="button" class="lang-btn" :class="{ active: selectedLang === 'KO' }" @click="selectedLang = 'KO'">{{ koLabel }}</button>
        <button type="button" class="lang-btn" :class="{ active: selectedLang === 'EN' }" @click="selectedLang = 'EN'">{{ enLabel }}</button>
      </div>
    </div>

    <button type="button" class="apply-btn" @click="applySetting">{{ t('countryPanel.apply') }}</button>
    <p v-if="appliedMessage" class="apply-message">{{ appliedMessage }}</p>
  </div>
</template>

<style scoped>
.panel-content {
  @apply space-y-3 rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.search-wrap {
  @apply rounded border border-slate-700 bg-slate-900/80 p-2;
}

.search-input {
  @apply w-full bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500;
}

.country-grid {
  @apply grid max-h-64 grid-cols-3 gap-2 overflow-y-auto pr-1;
}

.country-btn {
  @apply flex flex-col items-center gap-1 rounded border border-slate-700 bg-slate-900/70 p-2 text-xs text-slate-200;
}

.country-btn.active {
  @apply border-cyan-400 text-cyan-300;
}

.flag {
  @apply text-lg;
}

.name {
  @apply text-[11px];
}

.section-title {
  @apply mb-1 text-xs font-semibold text-slate-300;
}

.lang-wrap {
  @apply rounded border border-slate-700 bg-slate-900/70 p-2;
}

.lang-grid {
  @apply grid grid-cols-2 gap-2;
}

.lang-btn {
  @apply rounded border border-slate-700 px-3 py-2 text-sm text-slate-200;
}

.lang-btn.active {
  @apply border-cyan-400 text-cyan-300;
}

.apply-btn {
  @apply w-full rounded border border-cyan-500 bg-cyan-600/10 py-2 text-sm font-semibold text-cyan-200;
}

.apply-message {
  @apply text-xs text-cyan-300;
}
</style>
