<script setup lang="ts">
import { computed, onMounted, onUnmounted } from "vue";
import { storeToRefs } from "pinia";
import { usePerformanceStore } from "@/stores/performance/performance.store";
import { useI18n } from "vue-i18n";

const PERFORMANCE_REFRESH_MS = 60000;

const performanceStore = usePerformanceStore();
const { solarSavings, loading } = storeToRefs(performanceStore);
const { t, locale } = useI18n();

const clamp = (value: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, value));

const safeNumber = (value: number | null | undefined): number => {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  return value;
};

const formatNumber = (value: number, maximumFractionDigits = 0): string => {
  const resolvedLocale = locale.value.startsWith("en") ? "en-US" : "ko-KR";
  return value.toLocaleString(resolvedLocale, { maximumFractionDigits });
};

const savingsWon = computed(() =>
  Math.round(safeNumber(solarSavings.value?.savings_won)),
);
const solarGenerationKwh = computed(() =>
  safeNumber(solarSavings.value?.solar_generation_kwh),
);
const avoidedGridKwh = computed(() =>
  safeNumber(solarSavings.value?.avoided_grid_kwh),
);
const avgTariffWonPerKwh = computed(() =>
  safeNumber(solarSavings.value?.avg_tariff_won_per_kwh),
);

const selfUseRate = computed(() => {
  const explicitRate = safeNumber(solarSavings.value?.self_use_ratio_pct);
  if (explicitRate > 0) return explicitRate;
  if (solarGenerationKwh.value <= 0) return 0;
  return (avoidedGridKwh.value / solarGenerationKwh.value) * 100;
});

const hasPerformanceData = computed(() => {
  return (
    savingsWon.value > 0 ||
    solarGenerationKwh.value > 0 ||
    avoidedGridKwh.value > 0
  );
});

const gaugeRate = computed(() => clamp(selfUseRate.value, 0, 100));

const gaugeArc = computed(() => {
  const radius = 82;
  const circumference = Math.PI * radius;
  const offset = circumference * (1 - gaugeRate.value / 100);
  return { circumference, offset };
});

const formattedSaving = computed(
  () => `${formatNumber(savingsWon.value)} ${t("kpi.units.won")}`,
);
const formattedSolarGeneration = computed(
  () => `${formatNumber(solarGenerationKwh.value, 1)} kWh`,
);
const formattedAvoidedGrid = computed(
  () => `${formatNumber(avoidedGridKwh.value, 1)} kWh`,
);
const formattedAvgTariff = computed(
  () =>
    `${formatNumber(avgTariffWonPerKwh.value, 1)} ${t("kpi.units.won")}/kWh`,
);
const formattedSelfUseRate = computed(
  () => `${formatNumber(gaugeRate.value, 1)}%`,
);

const tariffBasisText = computed(() => {
  return solarSavings.value?.tariff_basis || t("aiPerformance.meta.tariff");
});

const metaText = computed(() => {
  if (loading.value && !hasPerformanceData.value)
    return t("aiPerformance.loading");
  if (!hasPerformanceData.value) return t("aiPerformance.meta.empty");
  return t("aiPerformance.meta.formula", {
    solar: formattedSolarGeneration.value,
    offset: formattedAvoidedGrid.value,
  });
});

let refreshTimer: ReturnType<typeof window.setInterval> | null = null;

const refreshPerformance = (): void => {
  void performanceStore.fetchSolarSavings(undefined, "month");
};

onMounted(() => {
  refreshPerformance();
  refreshTimer = window.setInterval(refreshPerformance, PERFORMANCE_REFRESH_MS);
});

onUnmounted(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
});
</script>

<template>
  <section class="panel-card">
    <h3 class="title">
      {{ t("aiPerformance.title") }}
      <span class="sub-title">({{ t("common.thisMonth") }})</span>
    </h3>

    <div class="gauge-card">
      <div
        class="gauge-wrap"
        role="img"
        :aria-label="t('aiPerformance.ariaLabel')"
      >
        <svg
          viewBox="0 0 220 140"
          class="gauge-svg"
          preserveAspectRatio="xMidYMid meet"
        >
          <path class="track" d="M 28 112 A 82 82 0 0 1 192 112" />
          <path
            class="progress"
            d="M 28 112 A 82 82 0 0 1 192 112"
            :stroke-dasharray="gaugeArc.circumference"
            :stroke-dashoffset="gaugeArc.offset"
          />
        </svg>

        <div class="gauge-center">
          <p class="amount">{{ formattedSaving }}</p>
          <p class="amount-label">{{ t("aiPerformance.savingLabel") }}</p>
        </div>
      </div>

      <div class="gauge-footer">
        <div class="footer-item">
          <p class="footer-label">{{ t("aiPerformance.solarOffset") }}</p>
          <p class="footer-value">{{ formattedAvoidedGrid }}</p>
        </div>
        <div class="footer-item align-right">
          <p class="footer-label">{{ t("aiPerformance.avgUnitPrice") }}</p>
          <p class="footer-value">{{ formattedAvgTariff }}</p>
        </div>
      </div>
    </div>

    <p class="meta">
      {{ metaText }}
      <template v-if="hasPerformanceData">
        · {{ t("aiPerformance.selfUseRate") }} {{ formattedSelfUseRate }} ·
        {{ tariffBasisText }}
      </template>
    </p>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-3 text-slate-100;
}

.title {
  @apply mb-2 font-semibold text-sm;
}

.sub-title {
  @apply ml-1 text-xs font-normal text-slate-400;
}

.gauge-card {
  @apply rounded border border-slate-700 bg-slate-950/60 p-2;
}

.gauge-wrap {
  @apply relative;
}

.gauge-svg {
  @apply h-28 w-full;
}

.track {
  fill: none;
  stroke: rgba(148, 163, 184, 0.35);
  stroke-width: 14;
  stroke-linecap: round;
}

.progress {
  fill: none;
  stroke: #5b8dff;
  stroke-width: 14;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.35s ease;
}

.gauge-center {
  @apply pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-4;
}

.amount {
  @apply text-lg font-semibold text-cyan-200;
}

.amount-label {
  @apply mt-1 text-[10px] text-slate-400;
}

.gauge-footer {
  @apply mt-1 grid grid-cols-2 gap-2 border-t border-slate-700 pt-2;
}

.footer-item {
  @apply min-w-0;
}

.align-right {
  @apply text-right;
}

.footer-label {
  @apply text-[11px] text-slate-400;
}

.footer-value {
  @apply mt-0.5 text-sm font-semibold text-slate-100;
}

.meta {
  @apply mt-2 text-[10px] text-slate-500;
}
</style>
