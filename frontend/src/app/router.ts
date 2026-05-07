import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

/**
 * 라우터 설정
 * 
 * 페이지 라우트:
 * - OverviewPage: 개요 (대시보드 메인)
 * - DetailPage: 상세 보기
 * - TopologyPage: 토폴로지 (설비 배치)
 * - ForecastPage: 예측 (AI 예측)
 * - RecommendationPage: 권장 조치 (AI 권장)
 * - AlarmPage: 알람/비상
 * - HistoryPage: 이력 (과거 데이터)
 */

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'overview',
    component: () => import('@/pages/OverviewPage.vue'),
    meta: { title: '개요', icon: '📊' }
  },
  {
    path: '/detail',
    name: 'detail',
    component: () => import('@/pages/DetailPage.vue'),
    meta: { title: '상세', icon: '📋' }
  },
  {
    path: '/topology',
    name: 'topology',
    component: () => import('@/pages/TopologyPage.vue'),
    meta: { title: '토폴로지', icon: '🔌' }
  },
  {
    path: '/forecast',
    name: 'forecast',
    component: () => import('@/pages/ForecastPage.vue'),
    meta: { title: '예측', icon: '📈' }
  },
  {
    path: '/recommendation',
    name: 'recommendation',
    component: () => import('@/pages/RecommendationPage.vue'),
    meta: { title: '권장 조치', icon: '💡' }
  },
  {
    path: '/alarm',
    name: 'alarm',
    component: () => import('@/pages/AlarmPage.vue'),
    meta: { title: '알람', icon: '🔔' }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/pages/HistoryPage.vue'),
    meta: { title: '이력', icon: '📜' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 라우트 메뉴 정보 (사이드바용)
export const menuItems = routes.map(route => ({
  path: route.path,
  name: route.name as string,
  title: route.meta?.title as string,
  icon: route.meta?.icon as string
}))

export default router