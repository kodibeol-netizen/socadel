<template>
  <div class="page-container">
    <div class="container">
      <h2>📦 Traitement Automatique</h2>
      <div class="info-file">Fichier actuel : {{ nomFichier }}</div>
      
      <div class="progress-bar-container">
        <!-- La largeur de la barre dépend de la variable progression -->
        <div class="progress-bar" :style="{ width: progression + '%' }"></div>
      </div>
      
      <div class="status-text">{{ statut }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// Variables réactives (si elles changent, l'écran se met à jour automatiquement)
const nomFichier = ref('Analyse en cours...')
const progression = ref(0)
const statut = ref('Connexion au serveur Python...')

// Fonction qui va appeler notre API Python
const démarrerTraitement = async () => {
  try {
    // Étape A : On demande au backend si tout va bien
    const reponse = await fetch('http://localhost:8000/api/traitement')

    const donnees = await reponse.json()
    
    // Étape B : Si Python répond, on met à jour notre interface
    statut.value = donnees.message
    progression.value = 100 // On met la barre à 100% pour le test
    nomFichier.value = "Aucun fichier pour le moment"
    
  } catch (erreur) {
    statut.value = "Erreur : Impossible de contacter le serveur Python."
    console.error(erreur)
  }
}

// Cette fonction se lance automatiquement dès que la page s'affiche
onMounted(() => {
  démarrerTraitement()
})
</script>

<style scoped>
.page-container {
  font-family: sans-serif;
  background: #f4f7f6;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  margin: 0;
}
.container {
  background: white;
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
  width: 500px;
  text-align: center;
}
.progress-bar-container {
  background: #e0e0e0;
  border-radius: 20px;
  height: 20px;
  width: 100%;
  overflow: hidden;
  margin-top: 20px;
}
.progress-bar {
  background: linear-gradient(90deg, #2ecc71, #27ae60);
  height: 100%;
  transition: width 0.5s ease;
}
.status-text {
  margin-top: 15px;
  font-size: 14px;
  color: #555;
  font-weight: bold;
}
.info-file {
  color: #2980b9;
  font-size: 16px;
  margin-bottom: 10px;
  font-weight: bold;
}
</style>
