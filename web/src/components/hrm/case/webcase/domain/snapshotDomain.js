export function normalizeTargetSnapshot(snapshot) {
  if (!snapshot) {
    return null;
  }
  const context = isPlainObject(snapshot.context) ? snapshot.context : {};
  return {
    targetSnapshotId: snapshot.targetSnapshotId || snapshot.target_snapshot_id,
    fingerprint: snapshot.fingerprint || '',
    elementText: snapshot.elementText || snapshot.element_text || '',
    stableScore: Number(snapshot.stableScore ?? snapshot.stable_score ?? 0),
    context: {
      pageUrl: context.pageUrl || context.page_url || '',
      frameUrl: context.frameUrl || context.frame_url || '',
      frameChain: Array.isArray(context.frameChain || context.frame_chain)
        ? cloneData(context.frameChain || context.frame_chain)
        : [],
      shadowChain: Array.isArray(context.shadowChain || context.shadow_chain)
        ? cloneData(context.shadowChain || context.shadow_chain)
        : [],
    },
    locators: Array.isArray(snapshot.locators)
      ? snapshot.locators.map((item, index) => normalizeLocator(item, index))
      : [],
  };
}

export function createDefaultTargetSnapshot() {
  return {
    targetSnapshotId: undefined,
    fingerprint: '',
    elementText: '',
    stableScore: 0,
    context: createDefaultContext(),
    locators: [createDefaultLocator()],
  };
}
