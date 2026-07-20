<template>
  <div id="pointage-agent" class="card pointage-agent-card">
    <h3>👥 Pointage Jour par Jour - Agents</h3>
    
    <div class="table-responsive full-height-table">
      <table class="synthese-table">
        <thead>
          <tr>
            <th class="sticky-col header-double-size">Nom Agent</th>
            <th class="enterprise-header">Entreprise</th>
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
          <tr v-for="agent in agentsData" :key="agent.id" class="row-agence">
            <td class="sticky-col tree-cell">👤 {{ agent.name }}</td>
            <td class="enterprise-cell">{{ agent.enterprise }}</td>
            <td 
              v-for="day in daysInCycle" 
              :key="day"
              :class="['cell-interactive', { 'cell-active': isCellSelected(agent.id, day) }]"
              @click="$emit('cell-click', agent, day)"
            >
              {{ agent.days_data[day] || 0 }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  props: ['daysInCycle', 'agentsData', 'selectedDay', 'selectedCellsMap'],
  methods: {
    isCellSelected(agentId, day) {
      return !!this.selectedCellsMap[`agent-${agentId}-${day}`];
    }
  }
}
</script>

<style scoped>
.pointage-agent-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; display: flex; flex-direction: column; overflow: hidden; height: 100%; }
.pointage-agent-card h3 { margin-top: 0; color: #1e3a8a; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; font-size: 14px; }
.table-responsive { width: 100%; overflow-x: auto; max-height: 100%; overflow-y: auto; }
.synthese-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.synthese-table th, .synthese-table td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: center; white-space: nowrap; }
.synthese-table th { background-color: #f1f5f9; color: #1e3a8a; font-weight: 700; }
.sticky-col { position: sticky; left: 0; background-color: #ffffff; z-index: 5; text-align: left !important; box-shadow: 2px 0 5px rgba(0,0,0,0.05); min-width: 140px; }
.enterprise-header, .enterprise-cell { background-color: #f8fafc; font-weight: 500; color: #475569; font-size: 11px; text-align: left !important; }
.day-header { cursor: pointer; background-color: #f8fafc; }
.day-header:hover { background-color: #3b82f6; color: white !important; }
.day-header.is-selected { background: linear-gradient(135deg, #1e3a8a, #3b82f6); color: white !important; }
.cell-interactive { cursor: pointer; transition: all 0.1s ease; }
.cell-interactive:hover { background-color: rgba(59, 130, 246, 0.15) !important; font-weight: bold; }
.cell-active { background: #ea580c !important; color: #ffffff !important; font-weight: bold; }
.tree-cell { font-weight: 600; color: #334155; }
</style>
