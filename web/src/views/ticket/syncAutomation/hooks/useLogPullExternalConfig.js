import { ref, reactive, computed } from 'vue';
import { getLogPullExternalConfig, saveLogPullExternalConfig } from '@/api/ticket/logPull';
import { getTicketLogPullVendorStoreOptions } from '@/api/ticket/ticket';
import { listCredentialBindingOptions } from '@/api/system/credential';

/**
 * 日志拉取外部接口（环境分组+子环境+商家映射）配置管理 composable。
 * 独立于 useSyncConfig.js，不复用其表单结构。
 *
 * @param {Object} proxy - 当前组件实例代理，用于 $modal 消息提示
 */
export function useLogPullExternalConfig(proxy) {
  const loading = ref(false);
  const saving = ref(false);

  /** 所有商家选项列表，从 ticket.logPull.vendors 加载 */
  const allVendorOptions = ref([]);
  /** ticket_log_pull 类型的凭证绑定选项列表 */
  const credentialBindingOptions = ref([]);

  /** 分组配置 Map: { groupKey: { label, items: { itemKey: {label, insertUrl, pageUrl, credentialBindingId, origin, vendorFilter} }, defaultItem } } */
  const groups = reactive({});

  /** 生成的可用分组 key 列表，用于 UI 遍历 */
  const groupKeys = computed(() => Object.keys(groups));

  /**
   * 商家 vendorFilter 多选选项（用于 el-select multiple）。
   * 每个选项为 { label: '10001 - 商家A', value: '10001' }
   */
  const vendorFilterOptions = computed(() =>
    allVendorOptions.value.map(item => ({
      label: item.label,
      value: item.venderNo,
    }))
  );

  /**
   * 加载配置数据：分组配置 + 商家列表 + 凭证绑定选项
   */
  function loadConfig() {
    loading.value = true;
    return Promise.all([
      getLogPullExternalConfig().then(res => {
        const rawGroups = res?.data?.groups || {};
        // 清空并重新填充
        Object.keys(groups).forEach(k => delete groups[k]);
        Object.entries(rawGroups).forEach(([key, config]) => {
          groups[key] = normalizeGroupFromApi(config);
        });
      }),
      getTicketLogPullVendorStoreOptions().then(res => {
        const vendors = res?.data?.vendors || [];
        allVendorOptions.value = vendors.map(item => ({
          venderNo: String(item.venderNo || '').trim(),
          vendorName: String(item.vendorName || '').trim(),
          label: `${String(item.venderNo || '').trim()} - ${String(item.vendorName || '').trim()}`,
        })).filter(item => item.venderNo && item.vendorName);
      }),
      listCredentialBindingOptions('ticket_log_pull').then(res => {
        credentialBindingOptions.value = (res?.data || []).map(item => ({
          bindingId: item.bindingId,
          bindingName: item.bindingName || '',
          credentialName: item.credentialName || '',
          label: `${item.bindingName || '未命名'} / ${item.credentialName || '未知凭证'}`,
        }));
      }),
    ]).catch(err => {
      console.error('加载日志拉取外部接口配置失败:', err);
      proxy?.$modal?.msgError?.('加载配置失败: ' + (err?.msg || err?.message || '未知错误'));
    }).finally(() => {
      loading.value = false;
    });
  }

  /**
   * 将后端返回的单个分组配置归一化为响应式对象。
   */
  function normalizeGroupFromApi(rawGroup) {
    const g = rawGroup || {};
    const items = {};
    const rawItems = g.items || {};
    Object.entries(rawItems).forEach(([itemKey, itemConfig]) => {
      items[itemKey] = normalizeItemFromApi(itemConfig);
    });
    return reactive({
      label: String(g.label || '').trim(),
      items,
      defaultItem: String(g.defaultItem || '').trim() || null,
    });
  }

  /**
   * 将后端返回的单个子环境配置归一化。
   */
  function normalizeItemFromApi(rawItem) {
    const i = rawItem || {};
    const vendorFilter = Array.isArray(i.vendorFilter) ? [...i.vendorFilter] : ['*'];
    return reactive({
      label: String(i.label || '').trim(),
      insertUrl: String(i.insertUrl || '').trim(),
      pageUrl: String(i.pageUrl || '').trim(),
      credentialBindingId: String(i.credentialBindingId || '').trim(),
      origin: String(i.origin || '').trim(),
      vendorFilter,
    });
  }

  /**
   * 新增一个环境分组。
   */
  function addGroup() {
    const key = `group_${Date.now()}`;
    groups[key] = reactive({
      label: '',
      items: {},
      defaultItem: null,
    });
  }

  /**
   * 删除一个环境分组。
   */
  function removeGroup(groupKey) {
    proxy?.$modal
      ?.confirm?.(`确认删除环境分组「${groups[groupKey]?.label || groupKey}」？删除后不可恢复。`)
      .then(() => {
        delete groups[groupKey];
      })
      .catch(() => {});
  }

  /**
   * 在指定分组下新增一个子环境。
   */
  function addEnvItem(groupKey) {
    if (!groups[groupKey]) return;
    const key = `item_${Date.now()}`;
    groups[groupKey].items[key] = reactive({
      label: '',
      insertUrl: '',
      pageUrl: '',
      credentialBindingId: '',
      origin: '',
      vendorFilter: ['*'],
    });
  }

  /**
   * 删除指定分组下的子环境。
   */
  function removeEnvItem(groupKey, itemKey) {
    if (!groups[groupKey]) return;
    const itemLabel = groups[groupKey].items[itemKey]?.label || itemKey;
    proxy?.$modal
      ?.confirm?.(`确认删除子环境「${itemLabel}」？`)
      .then(() => {
        delete groups[groupKey].items[itemKey];
        // 如果被删除的是默认子环境，清除 defaultItem
        if (groups[groupKey].defaultItem === itemKey) {
          groups[groupKey].defaultItem = null;
        }
      })
      .catch(() => {});
  }

  /**
   * 修改分组展示名称。
   */
  function updateGroupLabel(groupKey, label) {
    if (groups[groupKey]) {
      groups[groupKey].label = label;
    }
  }

  /**
   * 修改子环境配置字段。
   */
  function updateItemConfig(groupKey, itemKey, field, value) {
    if (groups[groupKey]?.items[itemKey]) {
      groups[groupKey].items[itemKey][field] = value;
    }
  }

  /**
   * 构建保存用的纯净对象（去除响应式代理）。
   */
  function buildSavePayload() {
    const payload = {};
    Object.entries(groups).forEach(([groupKey, group]) => {
      const items = {};
      Object.entries(group.items).forEach(([itemKey, item]) => {
        items[itemKey] = {
          label: item.label,
          insertUrl: item.insertUrl,
          pageUrl: item.pageUrl,
          credentialBindingId: item.credentialBindingId,
          origin: item.origin,
          vendorFilter: [...item.vendorFilter],
        };
      });
      payload[groupKey] = {
        label: group.label,
        items,
        defaultItem: group.defaultItem || null,
      };
    });
    return { groups: payload };
  }

  /**
   * 保存配置到后端。
   */
  function handleSave() {
    saving.value = true;
    const payload = buildSavePayload();
    return saveLogPullExternalConfig(payload)
      .then(() => {
        proxy?.$modal?.msgSuccess?.('日志拉取外部接口配置已保存');
      })
      .catch(err => {
        proxy?.$modal?.msgError?.('保存失败: ' + (err?.msg || err?.message || '未知错误'));
        return Promise.reject(err);
      })
      .finally(() => {
        saving.value = false;
      });
  }

  /**
   * 获取指定分组下所有子环境的 key 列表（用于 defaultItem 下拉选项）。
   */
  function getItemKeysForGroup(groupKey) {
    const group = groups[groupKey];
    if (!group) return [];
    return Object.keys(group.items);
  }

  return {
    loading,
    saving,
    groups,
    groupKeys,
    allVendorOptions,
    vendorFilterOptions,
    credentialBindingOptions,
    loadConfig,
    addGroup,
    removeGroup,
    addEnvItem,
    removeEnvItem,
    updateGroupLabel,
    updateItemConfig,
    buildSavePayload,
    handleSave,
    getItemKeysForGroup,
  };
}
