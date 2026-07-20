<template>
  <div id="app-root">
    <!-- Cette balise magique indique à Vue d'afficher soit la connexion, soit le dashboard -->
    <router-view></router-view>
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
/* Réinitialisation globale propre */
html, body {
  margin: 0;
  padding: 0;
  background-color: #f8fafc;
  height: 100%;
}
</style>
