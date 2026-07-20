<template>
  <div id="resultat-requete" class="card result-card">
    <div class="result-header-inline">
      <h3>📋 Résultats de la Requête</h3>
      
      <!-- Commutateur de source d'image intégré dans l'en-tête du tableau -->
      <div class="image-source-toggle">
        <span class="toggle-label">🌐 Source des photos :</span>
        <button 
          @click="$emit('update:imageSource', 'online')" 
          :class="['btn-toggle-src', { active: imageSource === 'online' }]"
        >
          En Ligne (Serveur)
        </button>
        <button 
          @click="$emit('update:imageSource', 'local')" 
          :class="['btn-toggle-src', { active: imageSource === 'local' }]"
        >
          En Local (Disque)
        </button>
      </div>
    </div>
    
    <div class="table-responsive">
      <table class="query-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Région</th>
            <th>Agence</th>
            <th>Itinéraire</th>
            <th>Entreprise</th>
            <th>Agent</th>
            <th>Matricule</th>
            <th>Action</th>
            
            <th v-if="visibleColumns.includes('contrat')">Contrat</th>
            <th v-if="visibleColumns.includes('compteur')">Compteur</th>
            <th v-if="visibleColumns.includes('code-bare')">Code-barre</th>
            <th v-if="visibleColumns.includes('nom client')">Nom Client</th>
            <th v-if="visibleColumns.includes('pl')">PL</th>

            <th>Date Soumission</th>
            <th>Date Réalisation</th>
            <th>Photo</th>
            <th>Téléphone</th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="row in results" 
            :key="row.id"
            :class="['row-selectable', { 'row-is-selected': selectedRowId === row.id }]"
            @click="$emit('select-row', row.id)"
          >
            <td class="text-bold">{{ row.id }}</td>
            <td>{{ row.region }}</td>
            <td>{{ row.agency }}</td>
            <td>{{ row.itinerary }}</td>
            <td>{{ row.enterprise }}</td>
            <td>{{ row.agent }}</td>
            <td class="monospace-text">{{ row.matricule }}</td>
            <td><span class="badge-action">{{ row.action }}</span></td>
            
            <td v-if="visibleColumns.includes('contrat')">{{ row.extra_data.contrat }}</td>
            <td v-if="visibleColumns.includes('compteur')">{{ row.extra_data.compteur }}</td>
            <td v-if="visibleColumns.includes('code-bare')" class="monospace-text">{{ row.extra_data.barcode }}</td>
            <td v-if="visibleColumns.includes('nom client')">{{ row.extra_data.client_name }}</td>
            <td v-if="visibleColumns.includes('pl')">{{ row.extra_data.pl }}</td>

            <td class="monospace-text">{{ row.date_submit }}</td>
            <td class="monospace-text">{{ row.date_action }}</td>
            <td>
              <!-- Bouton dynamique affichant la source sélectionnée au survol/clic -->
              <div class="photo-placeholder-box" @click.stop="viewPhoto(row)">
                {{ imageSource === 'online' ? '🌐 Voir En ligne' : '💻 Voir Cliché Local' }}
              </div>
            </td>
            <td>{{ row.phone }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    results: { type: Array, default: () => [] },
    visibleColumns: { type: Array, default: () => [] },
    selectedRowId: { type: [Number, String], default: null },
    imageSource: { type: String, default: 'online' }
  },
  methods: {
    viewPhoto(row) {
      // Détermination de l'URL cible selon le choix de l'utilisateur
      const url = this.imageSource === 'online'
        ? `https://n0c.world{row.photo_name}`
        : `http://localhost:8888/photos/${row.photo_name}`;
      
      console.log(`[Photo View Trigger] Ouverture de la photo depuis la source : ${url}`);
      window.open(url, '_blank');
    }
  }
}
</script>

<style scoped>
.result-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; text-align: left; }
.result-header-inline { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-bottom: 12px; }
.result-card h3 { margin: 0; color: #1e3a8a; font-size: 14px; }
.table-responsive { width: 100%; overflow-x: auto; max-height: 400px; overflow-y: auto; }
.query-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.query-table th, .query-table td { border: 1px solid #e2e8f0; padding: 8px 10px; text-align: center; white-space: nowrap; }
.query-table th { background-color: #f1f5f9; color: #1e3a8a; }
.monospace-text { font-family: 'Courier New', monospace; font-size: 11px; }
.text-bold { font-weight: bold; color: #3b82f6; }
.badge-action { background-color: #1e3a8a; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; }
.photo-placeholder-box { background-color: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: 600; text-align: center; }
.photo-placeholder-box:hover { background-color: #dcfce7; }

/* Style des lignes sélectionnables */
.row-selectable { cursor: pointer; transition: background-color 0.15s ease; }
.row-selectable:hover { background-color: #f8fafc; }

/* Style de la LIGNE ACTIVE à SÉLECTION UNIQUE (Bleu ciel discret pour la clarté) */
.row-is-selected { background-color: #e0f2fe !important; border-left: 4px solid #0284c7; font-weight: 500; }

/* Commutateur de source */
.image-source-toggle { display: flex; align-items: center; gap: 6px; }
.toggle-label { font-size: 11px; font-weight: 600; color: #64748b; }
.btn-toggle-src { padding: 4px 10px; font-size: 11px; border: 1px solid #cbd5e1; background-color: #ffffff; color: #475569; cursor: pointer; border-radius: 4px; font-weight: 500; transition: all 0.1s; }
.btn-toggle-src:hover { background-color: #f1f5f9; }
.btn-toggle-src.active { background-color: #3b82f6; color: white; border-color: #3b82f6; font-weight: 600; }
</style>
