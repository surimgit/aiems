<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { DEFAULT_SITE_ID } from '@/app/config'
import { getSiteLoadProfile, saveSiteLoadProfile } from '@/api/ai.client'
import CountryLanguagePanel from './CountryLanguagePanel.vue'

const { t } = useI18n()

const promptText = ref('')
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const resultMessage = ref('')
const updatedAt = ref<string | null>(null)

const canSave = computed(() => promptText.value.trim().length > 0 && !saving.value)

const formatUpdatedAt = computed(() => {
  if (!updatedAt.value) return ''
  const date = new Date(updatedAt.value)
  if (Number.isNaN(date.getTime())) return updatedAt.value
  return date.toLocaleString()
})

const loadProfile = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const profile = await getSiteLoadProfile(DEFAULT_SITE_ID)
    if (profile?.found && profile.prompt_text) {
      promptText.value = profile.prompt_text
      updatedAt.value = profile.updated_at ?? null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t('settingsPanel.loadProfile.error')
  } finally {
    loading.value = false
  }
}

const saveProfile = async () => {
  if (!canSave.value) return
  saving.value = true
  errorMessage.value = ''
  resultMessage.value = ''
  try {
    const result = await saveSiteLoadProfile({
      site_id: DEFAULT_SITE_ID,
      prompt_text: promptText.value.trim(),
      use_openai: true
    })
    updatedAt.value = result.updated_at ?? null
    resultMessage.value = result.changed ? t('settingsPanel.loadProfile.updated') : t('settingsPanel.loadProfile.unchanged')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t('settingsPanel.loadProfile.error')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadProfile()
})
</script>

<template>
  <div class="settings-panel">
    <section class="settings-section">
      <div class="section-head">
        <p class="section-title">{{ t('settingsPanel.loadProfile.title') }}</p>
        <span v-if="loading" class="section-meta">{{ t('settingsPanel.loadProfile.loading') }}</span>
        <span v-else-if="formatUpdatedAt" class="section-meta">{{ formatUpdatedAt }}</span>
      </div>

      <textarea
        v-model="promptText"
        class="prompt-input"
        rows="8"
        :placeholder="t('settingsPanel.loadProfile.placeholder')"
      />

      <button type="button" class="save-btn" :disabled="!canSave" @click="saveProfile">
        {{ saving ? t('settingsPanel.loadProfile.saving') : t('settingsPanel.loadProfile.save') }}
      </button>

      <p v-if="resultMessage" class="result-message">{{ resultMessage }}</p>
      <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
    </section>

    <section class="settings-section">
      <p class="section-title">{{ t('settingsPanel.regionLanguage') }}</p>
      <CountryLanguagePanel />
    </section>
  </div>
</template>

<style scoped>
.settings-panel {
  @apply space-y-4 text-sm text-slate-300;
}

.settings-section {
  @apply space-y-3;
}

.section-head {
  @apply flex items-center justify-between gap-2;
}

.section-title {
  @apply text-xs font-semibold uppercase tracking-wide text-slate-300;
}

.section-meta {
  @apply truncate text-xs text-slate-500;
}

.prompt-input {
  @apply min-h-44 w-full resize-y rounded border border-slate-700 bg-slate-950/70 p-3 text-sm leading-6 text-slate-100 outline-none placeholder:text-slate-500 focus:border-cyan-400;
}

.save-btn {
  @apply w-full rounded border border-cyan-500 bg-cyan-600/10 py-2 text-sm font-semibold text-cyan-200 transition-colors disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-900/50 disabled:text-slate-500;
}

.result-message {
  @apply text-xs text-cyan-300;
}

.error-message {
  @apply text-xs text-red-300;
}
</style>
