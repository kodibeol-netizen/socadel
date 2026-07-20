import { createApp } from 'vue'
import App from './App.vue'
import router from './router' // 💡 Indique à Vue d'aller lire votre fichier router/index.js

const app = createApp(App)

app.use(router) // 🔥 Active le routeur pour que les pages s'affichent enfin

app.mount('#app')

