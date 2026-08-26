import { createApp } from 'vue'
import { FrappeUI } from 'frappe-ui'
import { router } from './router'
import App from './App.vue'
import './style.css'

const app = createApp(App)
app.use(router)
app.use(FrappeUI)
app.mount('#app')
