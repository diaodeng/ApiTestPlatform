/*
* 点击组件以外的区域，关闭组件
* */

const vClickOutside = {
  mounted(el, binding) {
    el.clickOutsideEvent = function(event) {
      // 如果点击的元素不是绑定指令的元素及其子元素，则执行绑定的函数
      if (!(el === event.target || el.contains(event.target))) {
        binding.value();
      }
    };
    document.addEventListener('click', el.clickOutsideEvent);
  },
  unmounted(el) {
    document.removeEventListener('click', el.clickOutsideEvent);
  },
};

export default vClickOutside;