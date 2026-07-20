import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import obfuscator from 'vite-plugin-javascript-obfuscator'

export default defineConfig({
  // 🚀 INDISPENSABLE : Empêche la page blanche lors de l'hébergement par le main.exe
  base: './', 
  plugins: [
    vue(),
    obfuscator({
      compact: true,
      
      // Sécurité Framework : Désactivé pour que le routeur de changement de page ne crashe pas
      controlFlowFlattening: false, 
      deadCodeInjection: false,
      
      // Protection Algorithme : Activé pour chiffrer vos clés, vos textes et vos URL d'API
      stringArray: true,
      stringArrayEncoding: ['base64'], // Vos chaînes restent chiffrées en Base64
      stringArrayThreshold: 0.8        // Chiffre 80% des chaînes du projet
    })
  ]
})
