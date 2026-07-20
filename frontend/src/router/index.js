import { createRouter, createWebHistory } from 'vue-router'
// Importation stricte des deux composants présents dans votre dossier views
import LoginView from '../views/LoginView.vue'       
import HomeView from '../views/HomeView.vue'         
import AnalyticView from '../views/AnalyticView.vue'         

const routes = [
  {
    path: '/',
    name: 'login',
    component: LoginView
  },
  {
    path: '/stat',
    name: 'stat',
    component: AnalyticView,
    // Cette sécurité empêche d'ouvrir le projet 1 si on n'est pas connecté
    /*beforeEnter: (to, from, next) => {
      const token = localStorage.getItem('user-token')
      if (!token) {
        next({ name: 'login' })
      } else {
        next()
      }
    }*/
  },
  {
    path: '/home',
    name: 'home',
    component: HomeView,
    // Cette sécurité empêche d'ouvrir le projet 1 si on n'est pas connecté
    /*beforeEnter: (to, from, next) => {
      const token = localStorage.getItem('user-token')
      if (!token) {
        next({ name: 'login' })
      } else {
        next()
      }
    }*/
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
