import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import DashboardHeader from './components/DashboardHeader.vue';
import FilterSidebar from './components/FilterSidebar.vue';
import SyntheseTable from './components/SyntheseTable.vue';
import StatChart from './components/StatChart.vue';
import AgentPointageTable from './components/AgentPointageTable.vue';
import ClientPointageTable from './components/ClientPointageTable.vue';
import QueryResultTable from './components/QueryResultTable.vue';

export default {
  name: 'HomeView',
  components: { DashboardHeader, FilterSidebar, SyntheseTable, StatChart, AgentPointageTable, ClientPointageTable, QueryResultTable },
  data() {
    return {
      currentUsername: 'Utilisateur', selectedCycle: '', selectedDay: null, searchQuery: '', isLoadingCycles: false,
      cycles: [], syntheseTreeData: [], mockAgentsPointage: [], mockClientsPointage: [], mockQueryResults: [], selectedCellsMap: {},
      mockChartQuantities: [],
      
      isColMenuOpen: false,
      extraColOptions: ['contrat', 'compteur', 'code-bare', 'nom client', 'pl'],
      selectedExtraCols: ['contrat', 'compteur'],
      
      activeQueryResultId: null,
      selectedImageSource: 'online',
      
      isLoadingQuery: false,      // Gère l'affichage de la barre de chargement
      rawBackendResults: [],      // Stocke TOUT le résultat brut téléchargé du serveur
      searchQuery: '',            // Votre filtre de texte actuel

      // État de dimensionnement : 'normal' (40%/60%), 'half' (20%/80%), 'hidden' (0%/100%)
      leftPanelState: 'normal',
      mapObject: null,

      filters: { 
        regions: [], agencies: [], itineraries: [], users: [], matricules: [], enterprises: [], 
        dateSubmitStart: '', dateSubmitEnd: '', dateActionStart: '', dateActionEnd: '' 
      },
      listData: {
        regions: [
          { id: 'REG-1', name: "DRNEA - Nord Électrique" }, { id: 'REG-2', name: "DRE - Direction Est" },
          { id: 'REG-3', name: "DRSM - Sud & Mfoundi" }, { id: 'REG-4', name: "DRY - Yaoundé" }, { id: 'REG-5', name: "DRD - Douala" }
        ],
        agencies: [
          { id: 'AGC-1', name: "Agence de Koumassi" }, { id: 'AGC-2', name: "Agence de Bonanjo" },
          { id: 'AGC-3', name: "Agence de Mvolyé" }, { id: 'AGC-4', name: "Agence de Garoua" }, { id: 'AGC-5', name: "Agence de Bafoussam" }
        ],
        itineraries: [
          { id: 'ITI-1', name: "Itinéraire Réseau Centre" }, { id: 'ITI-2', name: "Itinéraire Zone Industrielle" },
          { id: 'ITI-3', name: "Axe Périphérique Nord" }, { id: 'ITI-4', name: "Secteur Résidentiel Est" }, { id: 'ITI-5', name: "Collecte Commerciale Ouest" }
        ],
        users: [
          { id: 'USR-1', username: "Agent_Douala_Central" }, { id: 'USR-2', username: "Agent_Yaounde_Axe1" },
          { id: 'USR-3', username: "Superviseur_Littoral" }, { id: 'USR-4', username: "Controleur_DRC" }, { id: 'USR-5', username: "Agent_Nord_05" }
        ],
        matricules: [
          { id: 'MAT-1', code: "ENEO-2026-0041" }, { id: 'MAT-2', code: "ENEO-2026-0098" },
          { id: 'MAT-3', code: "SOCA-2026-1452" }, { id: 'MAT-4', code: "ENEO-2026-0811" }, { id: 'MAT-5', code: "SOCA-2026-3021" }
        ],
        enterprises: [
          { id: 'ENT-1', name: "ENEO Cameroon S.A." }, { id: 'ENT-2', name: "SOCADEL Collect Sarl" },
          { id: 'ENT-3', name: "Sub-Contractor Alfa" }, { id: 'ENT-4', name: "Eneo Dist. Partner" }, { id: 'ENT-5', name: "Power Services S.A." }
        ]
      }
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
      
      // LOG HORS LIGNE (Traitement instantané en mémoire locale)
      if (this.selectedDay) {
        console.log(`%c[💻 ÉTAT : HORS LIGNE] Filtrage local activé pour le Jour J${day}. Zéro octet consommé sur internet. Analyse instantanée des données stockées dans la mémoire RAM de votre machine.`, "color: #10b981; font-weight: bold;");
      } else {
        console.log(`%c[💻 ÉTAT : HORS LIGNE] Désélection du jour. Réinitialisation de la vue sur l'ensemble des données du mois sans appel réseau.`, "color: #64748b; font-style: italic;");
      }
    },


    handleCellClick(row, d) { 
      const k = `${row.id}-${d}`; 
      this.selectedCellsMap[k] = !this.selectedCellsMap[k]; 
      this.selectedCellsMap = { ...this.selectedCellsMap }; 
    },

    handleAgentCellClick(ag, d) { 
      const k = `agent-${ag.id}-${d}`; 
      this.selectedCellsMap[k] = !this.selectedCellsMap[k]; 
      this.selectedCellsMap = { ...this.selectedCellsMap }; 
    },

    handleClientCellClick(cli, d) { 
      const k = `client-${cli.id}-${d}`; 
      this.selectedCellsMap[k] = !this.selectedCellsMap[k]; 
      this.selectedCellsMap = { ...this.selectedCellsMap }; 
    },

    handleQueryResultSelect(rowId) { 
      this.activeQueryResultId = this.activeQueryResultId === rowId ? null : rowId; 
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
        return;
      }
      this.selectedDay = null; 
      this.selectedCellsMap = {};

      // LOG EN LIGNE (Sollicite le réseau)
      console.log(`%c[📡 ÉTAT : EN LIGNE] Chargement initial demandé pour le cycle ${this.selectedCycle}... Requête envoyée au serveur distant nhbpky.n0c.world.`, "color: #3b82f6; font-weight: bold;");

      this.mockChartQuantities = Array.from({ length: 8 }, () => Math.floor(Math.random() * 200) + 10);
      
      // Simulation des Agents de pointage
      this.mockAgentsPointage = ["Fouda Jean", "Kamga Hervé", "Eboué Marie", "Moussa Ali", "Bella Alice"].map((name, i) => {
        const days = {}; for (let d = 1; d <= this.daysInSelectedCycle; d++) days[d] = Math.floor(Math.random() * 3);
        return { id: i + 1, name, enterprise: i % 2 === 0 ? 'SOCADEL' : 'ENEO', days_data: days };
      });

      // Simulation des Clients Pointage
      this.mockClientsPointage = Array.from({ length: 5 }, (_, i) => {
        const days = {}; for (let d = 1; d <= this.daysInSelectedCycle; d++) days[d] = Math.floor(Math.random() * 2);
        return { id: i + 1, contract: `M-245${i}10`, meter: `E-09${i}1`, barcode: `CB-774${i}2`, match: i % 2 === 0, days_data: days };
      });

      // Simulation de l'arbre SyntheseTreeData (9 régions, 10 agences, 10 itinéraires)
      const regionsAncre = ["DRNEA", "DRE", "DRSM", "DRY", "DRD", "DRONO", "DRSANO", "DRSOM", "DRC"];
      this.syntheseTreeData = regionsAncre.map((reg, rIdx) => {
        const agences = Array.from({ length: 10 }, (_, a) => ({ 
          id: `ag-${rIdx}-${a}`, name: `Agence ${a + 1}`, expanded: false, total: 240, last_submit: '2026-05-24 08:30', last_action: '2026-05-24 14:00', days_data: { 1: 12 }, 
          itineraries: Array.from({ length: 10 }, (_, it) => ({ id: `iti-${rIdx}-${a}-${it}`, name: `Itinéraire ${it + 1}`, total: 24, last_submit: '2026-05-24', last_action: '2026-05-24', days_data: { 1: 2 } })) 
        }));
        return { id: `reg-${rIdx}`, name: reg, expanded: rIdx === 0, total: 2400, last_submit: '2026-05-24 08:30', last_action: '2026-05-24 14:00', days_data: { 1: 120 }, agences };
      });
    },










    async handleSearch() {
      this.isLoadingQuery = true;
      console.log("Début de l'unique téléchargement global depuis le serveur...");

      try {
        // Appel réel à votre API Django Centralisé (Décommenter plus tard) :
        // this.rawBackendResults = await api.post('/record/search-global/', this.filters);
        
        // SIMULATION : On attend 2 secondes (bande passante lente) puis on charge la masse de données
        await new Promise(resolve => setTimeout(resolve, 2000));

        this.rawBackendResults = Array.from({ length: 50 }, (_, i) => {
          const dayRandom = String(Math.floor(Math.random() * this.daysInSelectedCycle) + 1).padStart(2, '0');
          return {
            id: 2000 + i,
            region: i % 2 === 0 ? "Littoral" : "Centre",
            agency: i % 2 === 0 ? "Koumassi" : "Mvolyé",
            itinerary: `Axe G${i}`,
            enterprise: i % 3 === 0 ? "SOCADEL" : "ENEO",
            agent: i % 2 === 0 ? "Kamga Hervé" : "Fouda Jean",
            matricule: "SOCA-1452",
            action: i % 4 === 0 ? "BRANCHEMENT" : i % 4 === 1 ? "INSPECTION" : "RECOUVREMENT",
            date_submit: `${this.selectedCycle}-${dayRandom} 10:14`,
            date_action: `${this.selectedCycle}-${dayRandom} 11:30`,
            phone: "677889900",
            photo_name: `photo_${2000 + i}.jpg`,
            extra_data: { contrat: `M-990${i}`, compteur: `E-88${i}`, barcode: `CB-55${i}`, client_name: "Client Eneo", pl: "PL-04" }
          };
        });

        console.log("Téléchargement fini ! Les 50 enregistrements sont stockés sur le PC de l'utilisateur.");

      } catch (error) {
        console.error("Erreur réseau :", error.message);
      } finally {
        this.isLoadingQuery = false;
      }
    }





  }
};