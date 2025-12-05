import {ref, computed} from 'vue';


export default function useVirtualScroll(rootRef, props) {
    const scrollTop = ref(0);


    const totalHeight = computed(() => props.rows.length * props.rowHeight);


    const visibleRows = computed(() => {
        const start = Math.floor(scrollTop.value / props.rowHeight);
        const end = start + 20; // buffer
        return props.rows.slice(start, end).map((row, i) => ({
            index: start + i,
            data: row,
            offsetTop: (start + i) * props.rowHeight,
        }));
    });


    function onScroll() {
        scrollTop.value = rootRef.value.scrollTop;
    }


    return {visibleRows, totalHeight, onScroll};
}