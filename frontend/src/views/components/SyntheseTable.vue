<template>
  <div id="tableau-synthese-cycle" class="card fluid-synthese-card">
    <h3>📊 Synthèse du Cycle (Quantites d'actions)</h3>
    
    <div v-if="!selectedCycle" class="placeholder-text">
      Sélectionnez un cycle pour charger le tableau de synthèse.
    </div>

    <div v-else class="table-responsive full-height-table">
      <table class="synthese-table">
        <thead>
          <tr>
            <th class="sticky-col">Arbre Structure</th>
            <th>Total</th>
            <th>Last Submit</th>
            <th>Last Action</th>
            <th 
              v-for="day in daysInCycle" 
              :key="day" 
              :class="['day-header', { 'is-selected': selectedDay === day }]"
              @click="$emit('select-day', day)"
            >
              J{{ day }}
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="region in treeData" :key="region.id">
            
            <!-- Niveau 1 : Région -->
            <tr class="row-region">
              <td class="sticky-col tree-cell" @click="toggleNode(region)">
                <span class="toggle-icon">{{ region.expanded ? '▼' : '▶' }}</span>
                📁 {{ region.name }}
              </td>
              <td class="text-bold">{{ region.total }}</td>
              <td class="datetime-cell">{{ region.last_submit }}</td>
              <td class="datetime-cell">{{ region.last_action }}</td>
              <td 
                v-for="day in daysInCycle" 
                :key="day"
                :class="['cell-interactive', { 'cell-active': isCellSelected(region.id, day) }]"
                @click="onCellClick(region, day)"
              >
                {{ region.days_data && region.days_data[day] !== undefined ? region.days_data[day] : 0 }}
              </td>
            </tr>

            <!-- Niveau 2 : Agences -->
            <template v-if="region.expanded && region.agences">
              <template v-for="agence in region.agences" :key="agence.id">
                <tr class="row-agence">
                  <td class="sticky-col tree-cell indent-1" @click="toggleNode(agence)">
                    <span class="toggle-icon">{{ agence.expanded ? '▼' : '▶' }}</span>
                    🏢 {{ agence.name }}
                  </td>
                  <td class="text-bold">{{ agence.total }}</td>
                  <td class="datetime-cell">{{ agence.last_submit }}</td>
                  <td class="datetime-cell">{{ agence.last_action }}</td>
                  <td 
                    v-for="day in daysInCycle" 
                    :key="day"
                    :class="['cell-interactive', { 'cell-active': isCellSelected(agence.id, day) }]"
                    @click="onCellClick(agence, day)"
                  >
                    {{ agence.days_data && agence.days_data[day] !== undefined ? agence.days_data[day] : 0 }}
                  </td>
                </tr>

                <!-- Niveau 3 : Itinéraires -->
                <template v-if="agence.expanded && agence.itineraries">
                  <tr v-for="itinerary in agence.itineraries" :key="itinerary.id" class="row-itinerary">
                    <td class="sticky-col tree-cell indent-2">📍 {{ itinerary.name }}</td>
                    <td>{{ itinerary.total }}</td>
                    <td class="datetime-cell">{{ itinerary.last_submit }}</td>
                    <td class="datetime-cell">{{ itinerary.last_action }}</td>
                    <td 
                      v-for="day in daysInCycle" 
                      :key="day"
                      :class="['cell-interactive', { 'cell-active': isCellSelected(itinerary.id, day) }]"
                      @click="onCellClick(itinerary, day)"
                    >
                      {{ itinerary.days_data && itinerary.days_data[day] !== undefined ? itinerary.days_data[day] : 0 }}
                    </td>
                  </tr>
                </template>

              </template>
            </template>

          </template>
        </tbody>
      </table>
    </div>

    <h3>📊 Synthèse du Cycle (Quantites d'images)</h3>
    
    <div v-if="!selectedCycle" class="placeholder-text">
      Sélectionnez un cycle pour charger le tableau de synthèse.
    </div>

    <div v-else class="table-responsive full-height-table">
      <table class="synthese-table">
        <thead>
          <tr>
            <th class="sticky-col">Arbre Structure</th>
            <th>Total</th>
            <th>Last Submit</th>
            <th>Last Action</th>
            <th 
              v-for="day in daysInCycle" 
              :key="day" 
              :class="['day-header', { 'is-selected': selectedDay === day }]"
              @click="$emit('select-day', day)"
            >
              J{{ day }}
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="region in treeData" :key="region.id">
            
            <!-- Niveau 1 : Région -->
            <tr class="row-region">
              <td class="sticky-col tree-cell" @click="toggleNode(region)">
                <span class="toggle-icon">{{ region.expanded ? '▼' : '▶' }}</span>
                📁 {{ region.name }}
              </td>
              <td class="text-bold">{{ region.total }}</td>
              <td class="datetime-cell">{{ region.last_submit }}</td>
              <td class="datetime-cell">{{ region.last_action }}</td>
              <td 
                v-for="day in daysInCycle" 
                :key="day"
                :class="['cell-interactive', { 'cell-active': isCellSelected(region.id, day) }]"
                @click="onCellClick(region, day)"
              >
                {{ region.days_data && region.days_data[day] !== undefined ? region.days_data[day] : 0 }}
              </td>
            </tr>

            <!-- Niveau 2 : Agences -->
            <template v-if="region.expanded && region.agences">
              <template v-for="agence in region.agences" :key="agence.id">
                <tr class="row-agence">
                  <td class="sticky-col tree-cell indent-1" @click="toggleNode(agence)">
                    <span class="toggle-icon">{{ agence.expanded ? '▼' : '▶' }}</span>
                    🏢 {{ agence.name }}
                  </td>
                  <td class="text-bold">{{ agence.total }}</td>
                  <td class="datetime-cell">{{ agence.last_submit }}</td>
                  <td class="datetime-cell">{{ agence.last_action }}</td>
                  <td 
                    v-for="day in daysInCycle" 
                    :key="day"
                    :class="['cell-interactive', { 'cell-active': isCellSelected(agence.id, day) }]"
                    @click="onCellClick(agence, day)"
                  >
                    {{ agence.days_data && agence.days_data[day] !== undefined ? agence.days_data[day] : 0 }}
                  </td>
                </tr>

                <!-- Niveau 3 : Itinéraires -->
                <template v-if="agence.expanded && agence.itineraries">
                  <tr v-for="itinerary in agence.itineraries" :key="itinerary.id" class="row-itinerary">
                    <td class="sticky-col tree-cell indent-2">📍 {{ itinerary.name }}</td>
                    <td>{{ itinerary.total }}</td>
                    <td class="datetime-cell">{{ itinerary.last_submit }}</td>
                    <td class="datetime-cell">{{ itinerary.last_action }}</td>
                    <td 
                      v-for="day in daysInCycle" 
                      :key="day"
                      :class="['cell-interactive', { 'cell-active': isCellSelected(itinerary.id, day) }]"
                      @click="onCellClick(itinerary, day)"
                    >
                      {{ itinerary.days_data && itinerary.days_data[day] !== undefined ? itinerary.days_data[day] : 0 }}
                    </td>
                  </tr>
                </template>

              </template>
            </template>

          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  props: ['selectedCycle', 'daysInCycle', 'treeData', 'selectedDay', 'selectedCellsMap'],
  methods: {
    toggleNode(node) { node.expanded = !node.expanded; },
    isCellSelected(rowId, day) { return !!this.selectedCellsMap[`${rowId}-${day}`]; },
    onCellClick(rowNode, day) { this.$emit('cell-click', rowNode, day); }
  }
}
</script>

<style scoped>
.fluid-synthese-card { flex: 1; height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.table-responsive { width: 100%; overflow-x: auto; max-height: 100%; overflow-y: auto; }
.synthese-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.synthese-table th, .synthese-table td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: center; white-space: nowrap; }
.synthese-table th { background-color: #f1f5f9; color: #1e3a8a; font-weight: 700; }
.sticky-col { position: sticky; left: 0; background-color: #ffffff; z-index: 5; text-align: left !important; box-shadow: 2px 0 5px rgba(0,0,0,0.05); min-width: 190px; }
.datetime-cell { font-family: 'Courier New', monospace; font-size: 11px; color: #334155; background-color: #fafafa; }
.day-header { cursor: pointer; background-color: #f8fafc; }
.day-header:hover { background-color: #3b82f6; color: white !important; }
.day-header.is-selected { background: linear-gradient(135deg, #1e3a8a, #3b82f6); color: white !important; }
.cell-interactive { cursor: pointer; transition: all 0.15s ease; }
.cell-interactive:hover { background-color: rgba(59, 130, 246, 0.15) !important; font-weight: bold; }
.cell-active { background: #ea580c !important; color: #ffffff !important; font-weight: bold; }
.tree-cell { cursor: pointer; user-select: none; font-weight: 600; }
.toggle-icon { display: inline-block; width: 15px; font-size: 10px; color: #64748b; }
.indent-1 { padding-left: 22px !important; background-color: #fcfcfc; }
.indent-2 { padding-left: 40px !important; background-color: #fafafa; font-weight: normal; }
.row-region { background-color: #f1f5f9; }
.row-region td.sticky-col { background-color: #f1f5f9; }
.row-agence { background-color: #ffffff; }
.row-itinerary { color: #475569; }
.card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; text-align: left; }
.card h3 { margin-top: 0; color: #1e3a8a; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; font-size: 14px; }
.placeholder-text { color: #64748b; font-size: 13px; font-style: italic; }
.text-bold { font-weight: bold; color: #1e3a8a; }
</style>
