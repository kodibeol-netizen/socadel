<template>
  <div class="filters-sidebar">
    

    <div id="filtre" class="card fixed-filter-card">
      <h3>🔍 Filtres Avancés</h3>
      <div class="filters-container-full">
        <div v-for="(label, key) in filterDefinitions" :key="key" class="form-group dropdown-filter">
          <button @click="toggleDropdown(key)" class="btn-dropdown" type="button">
            <span>{{ label }} ({{ filters[key].length }})</span>
            <span class="arrow">{{ activeDropdown === key ? '▴' : '▾' }}</span>
          </button>
          <div v-if="activeDropdown === key" class="custom-multiselect-container">
            <div v-for="item in listData[key]" :key="item.id" class="multiselect-item">
              <input type="checkbox" :value="item.id" v-model="filters[key]" />
              <span class="item-text">{{ item.name || item.username || item.code }}</span>
            </div>
          </div>
        </div>

        <!-- Date de Soumission Compacte -->
        <div class="form-group dropdown-filter">
          <button @click="toggleDropdown('dateSubmit')" class="btn-dropdown" type="button">
            <span>📅 Période Soumission</span>
            <span class="arrow">{{ activeDropdown === 'dateSubmit' ? '▴' : '▾' }}</span>
          </button>
          <div v-if="activeDropdown === 'dateSubmit'" class="custom-multiselect-container padding-box">
            <div class="date-inline-inputs">
              <input type="date" v-model="filters.dateSubmitStart" class="form-control compact-date" />
              <span class="date-sep">au</span>
              <input type="date" v-model="filters.dateSubmitEnd" class="form-control compact-date" />
            </div>
          </div>
        </div>

        <!-- Date de Réalisation Réintégrée -->
        <div class="form-group dropdown-filter">
          <button @click="toggleDropdown('dateAction')" class="btn-dropdown" type="button">
            <span>⚙️ Période Réalisation</span>
            <span class="arrow">{{ activeDropdown === 'dateAction' ? '▴' : '▾' }}</span>
          </button>
          <div v-if="activeDropdown === 'dateAction'" class="custom-multiselect-container padding-box">
            <div class="date-inline-inputs">
              <input type="date" v-model="filters.dateActionStart" class="form-control compact-date" />
              <span class="date-sep">au</span>
              <input type="date" v-model="filters.dateActionEnd" class="form-control compact-date" />
            </div>
          </div>
        </div>
      </div>
      <button @click="$emit('search')" class="btn-search" :disabled="!selectedCycle">Rechercher</button>
    </div>
  </div>
</template>

<script>
export default {
  props: ['selectedCycle', 'cycles', 'isLoading', 'listData', 'filters'],
  data() {
    return {
      activeDropdown: null,
      filterDefinitions: {
        regions: '📍 Régions', agencies: '🏢 Agences', itineraries: '🗺️ Itinéraires',
        users: '👥 Agents', matricules: '🆔 Matricules', enterprises: '🏭 Entreprises'
      }
    };
  },
  methods: {
    toggleDropdown(name) { this.activeDropdown = this.activeDropdown === name ? null : name; }
  }
}
</script>

<style scoped>
.filters-sidebar { display: flex; flex-direction: column; gap: 12px; height: 100%; }
.fixed-filter-card { flex: 1; display: flex; flex-direction: column; }
.dropdown-filter { position: relative; }
.btn-dropdown { width: 100%; padding: 7px 10px; background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 12px; color: #334155; display: flex; justify-content: space-between; align-items: center; cursor: pointer; font-weight: 500; }
.custom-multiselect-container { position: absolute; bottom: 100%; left: 0; width: 100%; border: 1px solid #cbd5e1; border-radius: 8px; max-height: 150px; overflow-y: auto; background: #ffffff; padding: 4px 0; z-index: 80; box-shadow: 0 -4px 10px rgba(0,0,0,0.1); }
.multiselect-item { display: flex; align-items: center; gap: 8px; padding: 6px 12px; font-size: 12px; cursor: pointer; }
.multiselect-item:hover { background-color: #f1f5f9; }
.padding-box { padding: 8px !important; }
.date-inline-inputs { display: flex; align-items: center; gap: 4px; }
.compact-date { padding: 2px 4px !important; font-size: 11px !important; border: 1px solid #cbd5e1; height: 26px !important; width: 105px !important; }
.date-sep { font-size: 11px; color: #64748b; font-weight: bold; }
.card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; text-align: left; }
.card h3 { margin: 0 0 8px 0; color: #1e3a8a; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; font-size: 13px; }
.form-control { width: 100%; padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 6px; }
.btn-search { width: 100%; padding: 8px; background: linear-gradient(135deg, #1e3a8a, #3b82f6); color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: auto; }
</style>
