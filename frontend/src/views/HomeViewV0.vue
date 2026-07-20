<template>
  <div class="traitement-container">
    <h2 class="main-title">📊 Tableau de Bord - Importation ODK</h2>

    <!-- 1. Sélection de la Date -->
    <div class="card selector-card">
      <label for="date-select" class="label-date">Sélectionner la date à traiter : </label>
      <input 
        type="date" 
        id="date-select" 
        v-model="dateCible" 
        :disabled="enCours"
        class="input-date"
      />
      <button 
        @click="demarrerTraitement" 
        :disabled="enCours" 
        class="btn-primary"
      >
        {{ enCours ? '⏳ Éxécution en cours...' : '🚀 Lancer le traitement' }}
      </button>
    </div>

    <!-- 2. État du traitement en direct et Progression -->
    <div v-if="enCours || messageStatut" class="card status-card">
      <h3>📡 État de la Synchronisation</h3>
      <p class="status-text"><strong>Dernier statut :</strong> {{ messageStatut }}</p>
      
      <div class="progress-bar-container">
        <div 
          class="progress-bar" 
          :style="{ width: progression + '%' }"
        >
          {{ progression }}%
        </div>
      </div>
    </div>

    <!-- 3. Console de Progression (Logs Réels) -->
    <div class="card console-card">
      <h4>💻 Console de progression (Flux Server-Sent Events)</h4>
      <div class="console-logs" ref="consoleBox">
        <div v-for="(log, idx) in logs" :key="idx" class="log-line">
          {{ log }}
        </div>
        <div v-if="logs.length === 0" class="log-empty">En attente de lancement...</div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'App',
  data() {
    return {
      dateCible: '2026-06-23',
      enCours: false,
      messageStatut: 'Prêt',
      progression: 0,
      logs: [],
      fluxEvenements: null
    }
  },
  methods: {
    demarrerTraitement() {
      if (!this.dateCible) return;

      this.enCours = true;
      this.progression = 0;
      this.messageStatut = 'Connexion au serveur Python...';
      this.logs = [];

      if (this.fluxEvenements) {
        this.fluxEvenements.close();
      }

      // Connexion à l'endpoint de streaming FastAPI
      const urlApi = `http://localhost:8000/api/traitement?date=${this.dateCible}`;
      this.fluxEvenements = new EventSource(urlApi);

      this.ajouterLog(`📡 Requête de streaming initiée pour le ${this.dateCible}`);

      // Écoute des messages envoyés par le serveur
      this.fluxEvenements.onmessage = (event) => {
        try {
          // ⚠️ CORRECTION CRITIQUE : On parse le JSON contenu dans event.data
          const donnees = JSON.parse(event.data);

          // 1. Cas d'erreur renvoyée par Python
          if (donnees.erreur) {
            this.messageStatut = donnees.erreur;
            this.ajouterLog(`❌ Erreur : ${donnees.erreur}`);
            this.arreterFlux();
            return;
          }

          // 2. Cas de mise à jour de statut textuelle
          if (donnees.statut) {
            this.messageStatut = donnees.statut;
            this.ajouterLog(`ℹ️ ${donnees.statut}`);
          }

          // 3. Cas de mise à jour de la progression globale
          if (donnees.progression !== undefined) {
            this.progression = parseInt(donnees.progression, 10);
          }

          // 4. Cas de fin de journée avec demande de redirection automatique
          if (donnees.action === 'redirection' && donnees.prochaine_date) {
            this.ajouterLog(`🔄 Journée terminée. Passage automatique au : ${donnees.prochaine_date}`);
            this.dateCible = donnees.prochaine_date;
            this.arreterFlux();
            
            // Relance automatique après 2 secondes
            setTimeout(() => { 
              this.demarrerTraitement(); 
            }, 2000);
          }

        } catch (e) {
          // Si le message n'est pas du JSON (texte brut issu de telecharger_fichiers)
          const texteBrut = event.data;
          this.ajouterLog(`📄 ${texteBrut}`);
          this.messageStatut = texteBrut;

          // Extraction de la progression texte (ex: "Fichier 1/5") si elle existe en brut
          if (texteBrut.includes('%')) {
            const matchPercent = texteBrut.match(/(\d+)%/);
            if (matchPercent) this.progression = parseInt(matchPercent[1], 10);
          }
        }
      };

      // Interception des coupures réseau ou de la fin du script
      this.fluxEvenements.onerror = () => {
        this.ajouterLog("🔌 Flux de streaming terminé.");
        this.enCours = false;
        if (this.fluxEvenements) this.fluxEvenements.close();
      };
    },

    arreterFlux() {
      if (this.fluxEvenements) {
        this.fluxEvenements.close();
        this.fluxEvenements = null;
      }
      this.enCours = false;
    },

    ajouterLog(texte) {
      const horodatage = new Date().toLocaleTimeString();
      this.logs.push(`[${horodatage}] ${texte}`);
      
      // Force l'ascenseur de la console à descendre automatiquement
      this.$nextTick(() => {
        const consoleElem = this.$refs.consoleBox;
        if (consoleElem) {
          consoleElem.scrollTop = consoleElem.scrollHeight;
        }
      });
    }
  },
  beforeUnmount() {
    this.arreterFlux();
  }
}
</script>

<style scoped>
.traitement-container {
  max-width: 900px;
  margin: 30px auto;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  padding: 0 20px;
}
.main-title {
  text-align: center;
  color: #1e293b;
  margin-bottom: 30px;
}
.card {
  background: #ffffff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  border: 1px solid #f1f5f9;
}
.selector-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
}
.label-date {
  font-weight: 600;
  color: #334155;
}
.input-date {
  padding: 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 15px;
  outline: none;
}
.btn-primary {
  background: #2563eb;
  color: white;
  border: none;
  padding: 11px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 15px;
  transition: background 0.2s;
}
.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}
.btn-primary:disabled {
  background: #cbd5e1;
  color: #94a3b8;
  cursor: not-allowed;
}
.progress-bar-container {
  background: #f8fafc;
  border-radius: 20px;
  overflow: hidden;
  height: 24px;
  border: 1px solid #e2e8f0;
  margin-top: 10px;
}
.progress-bar {
  background: #10b981;
  color: white;
  text-align: center;
  line-height: 22px;
  font-size: 13px;
  font-weight: 700;
  width: 0%;
  height: 100%;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.console-card {
  background: #0f172a;
  color: #f8fafc;
  border: none;
}
.console-logs {
  background: #020617;
  font-family: 'Courier New', Courier, monospace;
  padding: 15px;
  height: 280px;
  overflow-y: auto;
  border-radius: 6px;
  border: 1px solid #334155;
}
.log-line {
  color: #38bdf8;
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.5;
}
.log-empty {
  color: #64748b;
  text-align: center;
  line-height: 250px;
}
</style>
