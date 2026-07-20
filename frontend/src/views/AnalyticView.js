import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import DashboardHeader from './components/DashboardHeader.vue';
import SyntheseTable from './components/SyntheseTable.vue';
import StatChart from './components/StatChart.vue';

export default {
  name: 'HomeView',
  components: { DashboardHeader, SyntheseTable, StatChart },
  data() {
    return {
      currentUsername: 'Utilisateur',
      selectedCycle: '',
      selectedDay: null,
      searchQuery: '',
      isLoadingCycles: false,
      isLoadingSynthese: false,
      syntheseError: '',
      cycles: [],
      syntheseTreeData: [],
      selectedCellsMap: {},
      mockChartQuantities: [],
      rawBackendResults: [],
      leftPanelState: 'normal',
      mapObject: null
    };
  },
  computed: {
    daysInSelectedCycle() {
      if (!this.selectedCycle) return 0;
      const [year, month] = this.selectedCycle.split('-').map(Number);
      return new Date(year, month, 0).getDate();
    },
    contentGridStyle() {
      if (this.leftPanelState === 'hidden') return { gridTemplateColumns: '0% 100%' };
      if (this.leftPanelState === 'half') return { gridTemplateColumns: '20% 80%' };
      return { gridTemplateColumns: '70% 30%' };
    },

    // CE BLOC FILTRE EN LOCAL SUR LE PC SANS TOUCHER INTERNET :
    filteredQueryResults() {
      let dataset = this.rawBackendResults;

      // 1. Si un jour J1-J31 est activé au-dessus, on ne garde que les actions de ce jour
      if (this.selectedDay) {
        const dayString = String(this.selectedDay).padStart(2, '0');
        const targetDatePart = `${this.selectedCycle}-${dayString}`; // Ex: "2026-05-12"
        
        dataset = dataset.filter(row => row.date_action.startsWith(targetDatePart));
      }

      // 2. Si l'utilisateur saisit du texte dans la barre de recherche
      if (this.searchQuery.trim() !== '') {
        const query = this.searchQuery.toLowerCase();
        dataset = dataset.filter(row => {
          return row.agent.toLowerCase().includes(query) ||
                row.action.toLowerCase().includes(query) ||
                row.agency.toLowerCase().includes(query) ||
                row.matricule.toLowerCase().includes(query) ||
                row.extra_data.contrat.toLowerCase().includes(query);
        });
      }

      return dataset;
    }
  },

  mounted() {
    this.currentUsername = localStorage.getItem('user-name') || 'Utilisateur';
    this.fetchDynamicCycles();
    this.initLeafletMap();
  },
  methods: {
    initLeafletMap() {
      // Coordonnées centrées sur le Cameroun (Yaoundé / Douala)
      this.mapObject = L.map(this.$refs.leafletMap).setView([4.15, 11.5], 7);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
      }).addTo(this.mapObject);

      // Simulation de quelques marqueurs d'interventions Eneo
      const points = [
        { coords: [4.05, 9.7], label: "Douala - Branchement Actif" },
        { coords: [3.86, 11.51], label: "Yaoundé - Recouvrement Conforme" },
        { coords: [5.96, 10.15], label: "Bamenda - Dépannage Réseau" }
      ];
      points.forEach(p => {
        L.marker(p.coords).addTo(this.mapObject).bindPopup(p.label);
      });
    },
    
    setLeftPanelState(state) {
      this.leftPanelState = state;
      // Invalidation de la taille de la carte pour recalculer l'affichage Leaflet
      setTimeout(() => { 
        if (this.mapObject) this.mapObject.invalidateSize(); 
      }, 320);
    },

    handleLogout() { 
      localStorage.clear(); 
      this.$router.push({ name: 'login' }); 
    },

    goToProfile() { 
      this.$router.push({ name: 'account-settings' }); 
    },

    selectDay(day) {
      this.selectedDay = this.selectedDay === day ? null : day;
    },

    handleCellClick(row, d) {
      const key = `${row.id}-${d}`;
      this.selectedCellsMap[key] = !this.selectedCellsMap[key];
      this.selectedCellsMap = { ...this.selectedCellsMap };
    },

    async fetchDynamicCycles() {
      this.isLoadingCycles = true;
      const generated = [];
      const nomMois = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
      let currentDate = new Date(2025, 0, 1); 
      const endDate = new Date();

      while (currentDate <= endDate) {
        const year = currentDate.getFullYear(); 
        const month = String(currentDate.getMonth() + 1).padStart(2, '0');
        generated.push({ 
          id: generated.length + 1, 
          value: `${year}-${month}`, 
          label: `${nomMois[currentDate.getMonth()]} ${year}` 
        });
        currentDate.setMonth(currentDate.getMonth() + 1);
      }

      this.cycles = generated.reverse();
      this.selectedCycle = `${endDate.getFullYear()}-${String(endDate.getMonth() + 1).padStart(2, '0')}`;
      this.onCycleChange();
      this.isLoadingCycles = false;
    },

    async onCycleChange() {
      if (!this.selectedCycle) {
        this.syntheseTreeData = [];
        this.syntheseError = '';
        return;
      }
      this.selectedDay = null;
      this.selectedCellsMap = {};

      this.mockChartQuantities = Array.from({ length: 8 }, () => Math.floor(Math.random() * 200) + 10);
      await this.fetchSyntheseData(this.selectedCycle);
    },

    async fetchSyntheseData(cycle) {
      this.isLoadingSynthese = true;
      this.syntheseError = '';

      try {
        const response = await fetch(`http://127.0.0.1:8000/api/synthese?cycle=${encodeURIComponent(cycle)}`);
        if (!response.ok) {
          throw new Error(`Erreur réseau ${response.status}`);
        }

        const payload = await response.json();
        if (payload.erreur) {
          throw new Error(payload.erreur);
        }

        this.syntheseTreeData = this.buildSyntheseTree(payload.rows || []);
      } catch (error) {
        console.error('Erreur lors du chargement de la synthèse :', error);
        this.syntheseTreeData = [];
        this.syntheseError = error.message || 'Impossible de charger la synthèse.';
      } finally {
        this.isLoadingSynthese = false;
      }
    },

    buildSyntheseTree(rows) {
      const regionMap = new Map();
      const totalDays = this.daysInSelectedCycle || 1;

      rows.forEach((row) => {
        const regionName = row.ref_formulaire || 'Sans formulaire';
        const agencyName = row.bloc || 'Sans bloc';
        const itineraryName = `${row.agence || 'agence'} - ${agencyName}`;

        let region = regionMap.get(regionName);
        if (!region) {
          region = {
            id: `region-${regionName}`,
            name: regionName,
            expanded: true,
            total: 0,
            last_submit: row.last_submit || '',
            last_action: row.last_realisation || '',
            days_data: {},
            agences: []
          };
          regionMap.set(regionName, region);
        }

        let agency = region.agences.find(item => item.name === agencyName);
        if (!agency) {
          agency = {
            id: `agency-${regionName}-${agencyName}`,
            name: agencyName,
            expanded: false,
            total: 0,
            last_submit: row.last_submit || '',
            last_action: row.last_realisation || '',
            days_data: {},
            itineraries: []
          };
          region.agences.push(agency);
        }

        const daysData = {};
        for (let day = 1; day <= totalDays; day += 1) {
          const dayKey = `J${day}`;
          daysData[day] = Number(row[dayKey] || 0);
        }

        const itinerary = {
          id: `itinerary-${regionName}-${agencyName}-${row.periode}`,
          name: itineraryName,
          total: Number(row.total || 0),
          last_submit: row.last_submit || '',
          last_action: row.last_realisation || '',
          days_data: daysData
        };

        agency.itineraries.push(itinerary);
        agency.total += itinerary.total;
        agency.last_submit = agency.last_submit || itinerary.last_submit;
        agency.last_action = agency.last_action || itinerary.last_action;
        region.total += itinerary.total;
        region.last_submit = region.last_submit || itinerary.last_submit;
        region.last_action = region.last_action || itinerary.last_action;
      });

      return Array.from(regionMap.values()).map((region) => ({
        ...region,
        days_data: Object.fromEntries(
          Object.entries(region.agences.reduce((acc, agency) => {
            agency.itineraries.forEach((itinerary) => {
              Object.entries(itinerary.days_data).forEach(([day, value]) => {
                acc[day] = (acc[day] || 0) + Number(value || 0);
              });
            });
            return acc;
          }, {}))
        )
      }));
    },










  }
};