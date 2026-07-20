<template>
  <div id="stat-annee-cycle" class="card chart-card-container">
    <div class="chart-header-inline">
      <h3>📈 Statistiques — {{ isZoomed ? `${zoomedLabel}` : 'Performance' }}</h3>
      <button v-if="isZoomed" @click="resetZoom" class="btn-mini-reset">Vue globale</button>
    </div>
    <div class="chart-wrapper-box">
      <Bar :data="currentChartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script>
import { Bar } from 'vue-chartjs';
import { Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale } from 'chart.js';

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

export default {
  name: 'StatChart',
  components: { Bar },
  props: { actionsData: { type: Array, default: () => [] } },
  data() {
    return {
      isZoomed: false, zoomedIndex: null, zoomedLabel: '',
      labels: ['BRANCHEMENT', 'INSPECTION', 'DISTRIBUTION', 'RECOUVREMENT', 'NORMALISATION', 'DETECTION', 'RELEVE', 'DEPANNAGE']
    };
  },
  computed: {
    computedStackedData() {
      const baseValues = this.actionsData.length ? this.actionsData : [100, 80, 140, 90, 110, 60, 130, 75];
      return baseValues.map(total => {
        const bienRealise = Math.round(total * 0.7);
        const malExecute = Math.round(total * 0.1);
        const nonExecute = total - bienRealise - malExecute;
        return { total, bienRealise, malExecute, nonExecute };
      });
    },
    currentChartData() {
      if (this.isZoomed && this.zoomedIndex !== null) {
        const dObj = this.computedStackedData[this.zoomedIndex];
        return {
          labels: [this.zoomedLabel],
          datasets: [
            { label: 'Bien réalisé', backgroundColor: '#10b981', data: [dObj.bienRealise] },
            { label: 'Mal exécuté', backgroundColor: '#f59e0b', data: [dObj.malExecute] },
            { label: 'Non exécuté', backgroundColor: '#ef4444', data: [dObj.nonExecute] }
          ]
        };
      }
      return {
        labels: this.labels,
        datasets: [
          { label: 'Bien réalisé', backgroundColor: '#10b981', data: this.computedStackedData.map(d => d.bienRealise) },
          { label: 'Mal exécuté', backgroundColor: '#f59e0b', data: this.computedStackedData.map(d => d.malExecute) },
          { label: 'Non exécuté', backgroundColor: '#ef4444', data: this.computedStackedData.map(d => d.nonExecute) }
        ]
      };
    },
    chartOptions() {
      return {
        responsive: true, maintainAspectRatio: false,
        scales: { x: { stacked: true }, y: { stacked: true } },
        plugins: {
          tooltip: {
            mode: 'index',
            intersect: false,
            callbacks: {
              footer: (items) => {
                let total = 0;
                items.forEach(item => { total += item.parsed.y; });
                return `TOTAL : ${total}`;
              }
            }
          }
        },
        onClick: (e, elements) => {
          if (this.isZoomed || !elements.length) return;
          const idx = elements[0].index;
          this.zoomedIndex = idx; this.zoomedLabel = this.labels[idx]; this.isZoomed = true;
        }
      };
    }
  },
  methods: { resetZoom() { this.isZoomed = false; this.zoomedIndex = null; } }
};
</script>

<style scoped>
.chart-card-container { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; height: 100%; }
.chart-header-inline { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; }
.chart-card-container h3 { margin: 0; color: #1e3a8a; font-size: 13px; }
.btn-mini-reset { padding: 2px 6px; font-size: 10px; background-color: #1e3a8a; color: white; border: none; border-radius: 4px; cursor: pointer; }
.chart-wrapper-box { position: relative; flex: 1; min-height: 0; margin-top: 10px; }
</style>
