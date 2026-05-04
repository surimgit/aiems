/**
 * Dashboard API Client (조회 중심)
 * - ProjectDocs/11-api/dashboard-api.md 기준
 */

import { http } from './http'
import {
  mapEventDto,
  mapPowerSummaryDto,
  mapResourceDto,
  mapTopologyDto
} from '@/domain/mappers'
import type {
  EventDto,
  PlantStateDto,
  ResourceDto,
  TopologyDto
} from '@/types/api-contracts'
import type {
  AlarmData,
  DashboardData,
  ESSStatus,
  EventData,
  ForecastContract,
  PlantInfo,
  PlantState,
  PowerSummary,
  Recommendation,
  ResourceInfo,
  TopologyData
} from '@/types/common'

export const getPlants = async (): Promise<PlantInfo[]> => {
  return http.get<PlantInfo[]>('/api/plants')
}

export const getPowerSummary = async (siteId: string): Promise<PowerSummary> => {
  const dto = await http.get<PowerSummary>(`/api/plants/${siteId}/summary`)
  return mapPowerSummaryDto(dto)
}

export const getResources = async (siteId: string): Promise<ResourceInfo[]> => {
  const resources = await http.get<ResourceDto[]>(`/api/plants/${siteId}/resources`)
  return resources.map(mapResourceDto)
}

export const getPlantState = async (siteId: string): Promise<PlantState> => {
  const state = await http.get<PlantStateDto>(`/api/plants/${siteId}/state`)
  return {
    site_id: state.site_id,
    timestamp: state.timestamp,
    ess_list: state.ess_list,
    resources: state.resources?.map(mapResourceDto),
    summary: state.summary ? mapPowerSummaryDto(state.summary) : undefined
  }
}

export const getTopology = async (siteId: string): Promise<TopologyData> => {
  const dto = await http.get<TopologyDto>(`/api/plants/${siteId}/topology`)
  return mapTopologyDto(dto)
}

export const getEventList = async (siteId: string): Promise<EventData[]> => {
  const events = await http.get<EventDto[]>(`/api/plants/${siteId}/events`)
  return events.map(mapEventDto)
}

export const getAlarmList = async (siteId: string): Promise<AlarmData[]> => {
  return http.get<AlarmData[]>(`/api/plants/${siteId}/alarms`)
}

export const acknowledgeAlarmById = async (siteId: string, alarmId: string): Promise<void> => {
  await http.post<void>(`/api/plants/${siteId}/alarms/${alarmId}/ack`)
}

export const getForecastList = async (siteId: string): Promise<ForecastContract[]> => {
  return http.get<ForecastContract[]>(`/api/plants/${siteId}/forecasts`)
}

export const getRecommendationList = async (siteId: string): Promise<Recommendation[]> => {
  return http.get<Recommendation[]>(`/api/plants/${siteId}/recommendations`)
}

export const getEssStatusList = async (siteId: string): Promise<ESSStatus[]> => {
  const state = await getPlantState(siteId)
  if (state.ess_list) {
    return state.ess_list
  }
  return []
}

export const getDashboardData = async (siteId: string): Promise<DashboardData> => {
  const [powerSummary, essList, activeAlarms, forecastList, recommendations] = await Promise.all([
    getPowerSummary(siteId),
    getEssStatusList(siteId),
    getAlarmList(siteId),
    getForecastList(siteId),
    getRecommendationList(siteId)
  ])

  return {
    power_summary: powerSummary,
    ess_list: essList,
    active_alarms: activeAlarms,
    generation_forecast: forecastList,
    recommendations
  }
}

export const startPowerPolling = (
  siteId: string,
  interval: number,
  onData: (data: PowerSummary) => void,
  onError?: (error: Error) => void
): { stop: () => void } => {
  let running = true
  let timer: ReturnType<typeof setTimeout> | null = null

  const poll = async (): Promise<void> => {
    if (!running) {
      return
    }

    try {
      const data = await getPowerSummary(siteId)
      onData(data)
    } catch (error) {
      onError?.(error as Error)
    }

    if (running) {
      timer = setTimeout(() => {
        void poll()
      }, interval)
    }
  }

  void poll()

  return {
    stop: () => {
      running = false
      if (timer) {
        clearTimeout(timer)
      }
    }
  }
}

export default {
  getPlants,
  getPowerSummary,
  getResources,
  getPlantState,
  getTopology,
  getEventList,
  getAlarmList,
  acknowledgeAlarmById,
  getForecastList,
  getRecommendationList,
  getEssStatusList,
  getDashboardData,
  startPowerPolling
}
