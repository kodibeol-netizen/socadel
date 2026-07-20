<template>
  <div id="pointage-clients" class="card pointage-card">
    <h3>🏢 Pointage Jour par Jour - Clients</h3>
    
    <div class="table-responsive full-height-table">
      <table class="dashboard-data-table">
        <thead>
          <tr>
            <th class="sticky-col h-id">Contrat</th>
            <th>Compteur</th>
            <th>Code-barre</th>
            <th>Correspondance</th>
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
          <tr v-for="client in clientsData" :key="client.id">
            <td class="sticky-col cell-bold">📄 {{ client.contract }}</td>
            <td>{{ client.meter }}</td>
            <td class="font-code">{{ client.barcode }}</td>
            <td>
              <span :class="['status-badge', client.match ? 'match-ok' : 'match-ko']">
                {{ client.match ? 'Conforme' : 'Écart' }}
              </span>
            </td>
            <td 
              v-for="day in daysInCycle" 
              :key="day"
              :class="['cell-interactive', { 'cell-active': isCellSelected(client.id, day) }]"
              @click="$emit('cell-click', client, day)"
            >
              {{ client.days_data[day] || 0 }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  props: ['daysInCycle', 'clientsData', 'selectedDay', 'selectedCellsMap'],
  methods: {
    isCellSelected(clientId, day) {
      return !!this.selectedCellsMap[`client-${clientId}-${day}`];
    }
  }
}
</script>

<style scoped>
.pointage-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; display: flex; flex-direction: column; overflow: hidden; height: 100%; }
.pointage-card h3 { margin: 0 0 6px 0; color: #1e3a8a; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; font-size: 14px; }
.table-responsive { width: 100%; overflow-x: auto; max-height: 100%; overflow-y: auto; }
.dashboard-data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.dashboard-data-table th, .dashboard-data-table td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: center; white-space: nowrap; }
.dashboard-data-table th { background-color: #f1f5f9; color: #1e3a8a; font-weight: 700; }
.sticky-col { position: sticky; left: 0; background-color: #ffffff; z-index: 5; text-align: left !important; box-shadow: 2px 0 5px rgba(0,0,0,0.05); min-width: 110px; }
.font-code { font-family: 'Courier New', monospace; font-size: 11px; }
.day-header { cursor: pointer; background-color: #f8fafc; }
.day-header:hover { background-color: #3b82f6; color: white !important; }
.day-header.is-selected { background: linear-gradient(135deg, #1e3a8a, #3b82f6); color: white !important; }
.cell-interactive { cursor: pointer; transition: all 0.1s ease; }
.cell-interactive:hover { background-color: rgba(59, 130, 246, 0.15) !important; font-weight: bold; }
.cell-active { background: #ea580c !important; color: #ffffff !important; font-weight: bold; }
.cell-bold { font-weight: 600; color: #334155; }
.status-badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; color: white; }
.match-ok { background-color: #10b981; }
.match-ko { background-color: #ef4444; }
</style>
