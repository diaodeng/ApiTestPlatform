<template>
  <section class="app-main">
    <router-view v-slot="{ Component, route }">
      <transition name="fade-transform" mode="out-in">
        <keep-alive :include="tagsViewStore.cachedViews">
          <component v-if="!route.meta.link" :is="Component" :key="route.path"/>
        </keep-alive>
      </transition>
    </router-view>
    <iframe-toggle />
  </section>
</template>

<script setup>
import iframeToggle from "./IframeToggle/index"
import useTagsViewStore from '@/store/modules/tagsView'

const tagsViewStore = useTagsViewStore()
</script>

<style lang="scss" scoped>
.app-main {
  /* 50= navbar  50  */
  min-height: calc(100vh - 50px);
  width: 100%;
  position: relative;
  overflow: hidden;
}

.fixed-header + .app-main {
  padding-top: 50px;
}

.hasTagsView {
  .app-main {
    /* 84 = navbar + tags-view = 50 + 34 */
    min-height: calc(100vh - 84px);
  }

  .fixed-header + .app-main {
    padding-top: 84px;
  }
}
</style>

<style lang="scss">
// fix css style bug in open el-dialog
.el-popup-parent--hidden {
  .fixed-header {
    padding-right: 6px;
  }
}

::-webkit-scrollbar {
  width: 11px;
  height: 11px;
}

::-webkit-scrollbar-track {
  background-color: #f1f1f1;
  border-radius: 12px;
}

::-webkit-scrollbar-thumb {
  background-color: rgba(192, 192, 192, 0.49);
  border-radius: 12px;
  background-clip: padding-box;
  border: 2px dashed transparent;
}


::-webkit-scrollbar-thumb:hover {
  background: #c0c0c0;
  //background-color: #c0c0c0;
  //border-radius: 6px;
  //background-color: rgba(192, 192, 192, 0.8);
  //box-shadow: inset 6px 6px 6px hsl(0deg 0% 100% / 25%), inset -6px -6px 6px rgb(0 0 0 / 25%);
}
</style>

