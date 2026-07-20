<template>
  <div class="login-container">
    <!-- Section Gauche : Le Formulaire -->
    <div class="form-section">
      <div class="form-card">
        
        <!-- En-tête / Logo -->
        <div class="header-zone">
          <div class="logo-circle">S</div>
          <h2 class="company-title">SOCADEL S.A.</h2>
          <p class="company-subtitle">Exploitation d'Électricité au Cameroun</p>
          <p class="space-indicator">Espace Client & Partenaire Énergie</p>
        </div>

        <!-- Message d'erreur dynamique -->
        <div v-if="errorMessage" class="error-banner">
          <svg class="error-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
          <span>{{ errorMessage }}</span>
        </div>

        <!-- Formulaire -->
        <form @submit.prevent="handleLogin" class="auth-form">
          <div class="input-group">
            <label for="email">Numéro de contrat ou Matricule Collecteur</label>
            <input 
              id="email" 
              v-model="email" 
              type="text" 
              required 
              placeholder="Ex: naweu ou fofie"
            />
          </div>

          <div class="input-group">
            <label for="password">Mot de passe</label>
            <input 
              id="password" 
              v-model="password" 
              type="password" 
              required 
              placeholder="••••••••"
            />
          </div>

          <!-- Options -->
          <div class="form-options">
            <label class="checkbox-label">
              <input type="checkbox" />
              <span>Se souvenir de moi</span>
            </label>
            <a href="#" class="forgot-link">Mot de passe oublié ?</a>
          </div>

          <!-- Bouton Énergie -->
          <button type="submit" :disabled="isLoading" class="btn-submit">
            <span v-if="isLoading" class="spinner"></span>
            <span>{{ isLoading ? 'Connexion en cours...' : 'Accéder à mon espace' }}</span>
          </button>
        </form>

        <!-- Pied de page -->
        <div class="form-footer">
          <p>&copy; {{ currentYear }} SOCADEL S.A. Tous droits réservés.</p>
          <p class="regulation">Régulé par l'AER | République du Cameroun</p>
        </div>

      </div>
    </div>

    <!-- Section Droite : Grande Image d'accueil thématique Énergie -->
    <div class="image-section">
      <div class="image-overlay">
        <div class="overlay-content">
          <h1>L'énergie qui éclaire notre avenir</h1>
          <p>Une distribution stable et innovante pour le développement du Cameroun.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'LoginView',
  data() {
    return {
      email: '',
      password: '',
      isLoading: false,
      errorMessage: ''
    };
  },
  computed: {
    currentYear() {
      return new Date().getFullYear();
    }
  },
  methods: {
    async handleLogin() {
      if (!this.email || !this.password) return;
      
      this.isLoading = true;
      this.errorMessage = '';
      
      try {
        // Envoi de la requête réseau standard vers FastAPI sans dépendance externe
        const reponse = await fetch('https://kodibeol.pythonanywhere.com/api/auth/login', {
        //const reponse = await fetch('http://localhost:8000/api/auth/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            email: this.email,
            password: this.password
          })
        });

        const data = await reponse.json();

        // Si le serveur backend Python retourne un message d'erreur d'identifiant
        if (data.erreur) {
          this.errorMessage = data.erreur;
          this.isLoading = false;
          return;
        }

        // Si la connexion est validée par MySQL, on stocke la session
        if (data.detail && data.detail.token) {
          localStorage.setItem('user-token', data.detail.token);
          localStorage.setItem('user-name', data.detail.username);
          localStorage.setItem('token-expires-in', data.detail.expired_in);
          
          // Redirection vers votre tableau de bord de traitement ODK
          this.$router.push({ name: 'stat' });
        } else {
          this.errorMessage = 'Format de réponse serveur invalide.';
        }

      } catch (error) {
        this.errorMessage = 'Impossible de contacter le serveur de base de données SOCADEL.';
        console.error('Erreur Auth:', error);
      } finally {
        this.isLoading = false;
      }
    }
  }
};
</script>

<style scoped>
/* Conteneur principal plein écran */
.login-container {
  display: flex;
  min-height: 100vh;
  font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  background-color: #f4f7f6;
}

/* Section Formulaire (prend tout l'écran sur mobile, 45% sur PC) */
.form-section {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background-color: #ffffff;
}

.form-card {
  width: 100%;
  max-width: 400px;
}

/* En-tête */
.header-zone {
  text-align: center;
  margin-bottom: 35px;
}

.logo-circle {
  width: 65px;
  height: 65px;
  background: linear-gradient(135deg, #1e3a8a, #3b82f6);
  color: #ffffff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: bold;
  margin: 0 auto 15px auto;
  box-shadow: 0 10px 20px rgba(59, 130, 246, 0.3);
}

.company-title {
  font-size: 28px;
  color: #0f172a;
  margin: 0;
  font-weight: 800;
  letter-spacing: -0.5px;
}

.company-subtitle {
  font-size: 13px;
  color: #d97706; /* Couleur ambre électrique */
  font-weight: 600;
  text-transform: uppercase;
  margin: 5px 0 0 0;
  letter-spacing: 0.5px;
}

.space-indicator {
  font-size: 13px;
  color: #64748b;
  margin: 4px 0 0 0;
}

/* Bannière d'erreur API */
.error-banner {
  background-color: #fef2f2;
  border: 1px solid #fca5a5;
  color: #991b1b;
  padding: 12px;
  border-radius: 12px;
  margin-bottom: 20px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.error-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

/* Champs de saisie arrondis */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-group label {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.input-group input {
  padding: 13px 16px;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  font-size: 15px;
  outline: none;
  transition: all 0.3s ease;
}

.input-group input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.15);
}

/* Options */
.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  cursor: pointer;
}

.checkbox-label input {
  width: 16px;
  height: 16px;
  accent-color: #3b82f6;
}

.forgot-link {
  color: #2563eb;
  text-decoration: none;
  font-weight: 500;
}

.forgot-link:hover {
  text-decoration: underline;
}

/* Bouton bleu et jaune au survol */
.btn-submit {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: white;
  border: none;
  padding: 14px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.3);
  transition: all 0.3s ease;
}

.btn-submit:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 20px -3px rgba(37, 99, 235, 0.4);
  background: linear-gradient(135deg, #1d4ed8, #1e40af);
}

.btn-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Spinner de chargement */
.spinner {
  width: 18px;
  height: 18px;
  border: 3px solid rgba(255,255,255,0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Pied de page */
.form-footer {
  text-align: center;
  margin-top: 40px;
  font-size: 12px;
  color: #94a3b8;
  border-top: 1px solid #f1f5f9;
  padding-top: 20px;
}

.regulation {
  font-size: 10px;
  margin-top: 4px;
  font-weight: 600;
  color: #cbd5e1;
}

/* Section Droite : Image de fond (Invisible sur mobile, occupe 55% sur PC) */
.image-section {
  display: none;
  flex: 1.2;
  position: relative;
  background-image: url('https://unsplash.com');
  background-size: cover;
  background-position: center;
}

.image-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(15, 23, 42, 0.9), rgba(30, 58, 138, 0.4));
  display: flex;
  align-items: flex-end;
  padding: 60px;
}

.overlay-content {
  color: white;
  max-width: 500px; /* Correction appliquée ici */
}

.overlay-content h1 {
  font-size: 36px;
  font-weight: 800;
  margin-bottom: 15px;
  line-height: 1.2;
}

.overlay-content p {
  font-size: 16px;
  color: #e2e8f0;
  line-height: 1.5;
}

/* Media Query pour basculer en mode PC */
@media (min-width: 1024px) {
  .image-section {
    display: block;
  }
}
</style>
