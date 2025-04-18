<script setup>
import DictSelect from '@/components/select/dict_select.vue'
const props = defineProps({placeholder: {default: "请输入"}, options: {require: true, type: Array}})
const selectValue = defineModel()

const editing = ref(false);

function update(e) {
  editing.value = false;
}

const selectRef = ref(null);
const selectLabel = computed(()=>{
  const curVal = props.options.find((item)=>item.value === selectValue.value);
  return curVal?curVal.label:null;
});

watch(()=>editing.value, (newValue)=>{
  if (newValue){
    nextTick(()=>{
      selectRef.value.focus();
    });
  }
});




</script>

<template>

  <div class="cell" :title="selectLabel" @click="editing = true">
    <!--    <input-->
    <!--        v-if="editing"-->
    <!--        :value="cellData"-->
    <!--        @change="update"-->
    <!--        @blur="update"-->
    <!--        @vue:mounted="({ el }) => el.focus()"-->
    <!--    >-->
    <!--    <span v-else>{{ cellData }}</span>-->

    <template v-if="editing">
      <DictSelect :options-dict="options"
                  ref="selectRef"
                  v-model="selectValue"
                  :placeholder="placeholder"
                  @blur="()=>{editing = false}"
      ></DictSelect>
    </template>
    <template v-else>
      <span style="width: 100%;">{{ selectLabel }}</span>
    </template>
  </div>
</template>


<style scoped lang="scss">

</style>