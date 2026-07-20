<template>
  <header id="entete">
    <div class="brand-section">
      <div class="logo-circle">SC</div>
      <div class="brand-text">SOCADEL COLLECT</div>
    </div>
    <div class="user-menu-container">
      <div class="user-info" @click="isMenuOpen = !isMenuOpen">
        <span>👤 {{ username }}</span>
        <span class="caret">▾</span>
      </div>
      <ul v-if="isMenuOpen" class="user-dropdown">
        <li @click="$emit('profile')">⚙️ Configurer mon compte</li>
        <li @click="$emit('logout')" class="logout-item">🚪 Se déconnecter</li>
      </ul>
    </div>
  </header>
</template>

<script>
export default {
  props: ['username'],
  data() { return { isMenuOpen: false }; }
}
</script>

<style scoped>
#entete {
  background: linear-gradient(135deg, #1e3a8a, #3b82f6);
  color: white; padding: 10px 20px; display: flex;
  justify-content: space-between; align-items: center;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2); z-index: 20;
}
.brand-section { display: flex; align-items: center; gap: 12px; }
.brand-text { font-size: 20px; font-weight: bold; }
.logo-circle { width: 40px; height: 40px; background: rgba(255, 255, 255, 0.2); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; }
.user-menu-container { position: relative; }
.user-info { font-size: 14px; font-weight: 500; background: rgba(255, 255, 255, 0.15); padding: 8px 16px; border-radius: 20px; cursor: pointer; display: flex; align-items: center; gap: 8px; user-select: none; }
.user-info:hover { background: rgba(255, 255, 255, 0.25); }
.user-dropdown { position: absolute; top: 100%; right: 0; margin-top: 8px; background: white; border: 1px solid #cbd5e1; border-radius: 8px; box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1); padding: 8px 0; list-style: none; width: 200px; z-index: 30; text-align: left; }
.user-dropdown li { padding: 10px 16px; font-size: 13px; color: #334155; cursor: pointer; }
.user-dropdown li:hover { background-color: #f1f5f9; }
.user-dropdown .logout-item { color: #dc2626; border-top: 1px solid #f1f5f9; }
.user-dropdown .logout-item:hover { background-color: #fef2f2; }
</style>
