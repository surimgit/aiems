import { createPinia } from 'pinia'
import { createApp } from 'vue'
import AppShell from '@/app/AppShell.vue'
import i18n from '@/app/i18n'
import router from '@/app/router'
import './style.css'

const app = createApp(AppShell)

app.use(createPinia())
app.use(i18n)
app.use(router)
app.mount('#app')
