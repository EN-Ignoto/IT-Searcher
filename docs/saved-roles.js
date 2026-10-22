/* Saved-role snapshots survive feed expiry. No network requests or account. */
(function (root) {
  'use strict';
  function safeURL(value) {
    try { var u = new URL(String(value)); return /^https?:$/.test(u.protocol) ? u.href : ''; }
    catch (_) { return ''; }
  }
  function snapshot(value, savedAt) {
    var result = {};
    ['id', 'company', 'title', 'location', 'salary', 'posted', 'category', 'season'].forEach(function (k) {
      result[k] = String(value[k] || '').slice(0, 1000);
    });
    result.url = safeURL(value.url);
    result.savedAt = Number(savedAt || value.savedAt) || Date.now();
    return result;
  }
  function parse(text) {
    var result = Object.create(null), raw;
    try { raw = JSON.parse(text || '{}'); } catch (_) { return result; }
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return result;
    Object.keys(raw).forEach(function (id) {
      var value = raw[id];
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        result[id] = snapshot(Object.assign({}, value, {id: id}));
      } else if (typeof value === 'number' && value > 0) {
        // Legacy stars only stored a timestamp. Hydrate from a current row.
        result[id] = snapshot({id: id, title: 'Previously saved role — details unavailable'}, value);
      }
    });
    return result;
  }
  function reconcile(saved, current) {
    current.forEach(function (row) {
      var ids = row.ids || [row.id], value = saved[row.id];
      ids.forEach(function (id) { if (!value && saved[id]) value = saved[id]; });
      if (!value) return;
      saved[row.id] = snapshot(row, value.savedAt);
      ids.forEach(function (id) { if (id !== row.id) delete saved[id]; });
    });
    // Missing rows are deliberately retained until the user removes them.
    return saved;
  }
  var api = {safeURL: safeURL, snapshot: snapshot, parse: parse, reconcile: reconcile};
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SavedRoleStore = api;
})(typeof window === 'object' ? window : this);
