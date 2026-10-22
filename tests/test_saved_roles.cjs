const test = require('node:test');
const assert = require('node:assert/strict');
const store = require('../docs/saved-roles.js');
const role = {id:'a', company:'Acme', title:'IT Support', location:'Orlando, FL',
              posted:'2026-10-21', url:'https://example.com/job/1'};

test('saved snapshot survives refresh and removal from active feed', () => {
  const saved = store.parse('{}');
  saved.a = store.snapshot(role, 123);
  const reloaded = store.reconcile(store.parse(JSON.stringify(saved)), []);
  assert.equal(reloaded.a.url, role.url);
  assert.equal(reloaded.a.title, role.title);
  assert.equal(reloaded.a.savedAt, 123);
});
test('legacy numeric stars gain details and follow canonical requisition', () => {
  const saved = store.parse('{"old":123}');
  store.reconcile(saved, [{...role, ids:['a','old']}]);
  assert.equal(saved.a.savedAt, 123);
  assert.equal(saved.a.url, role.url);
  assert.equal(saved.old, undefined);
});
test('current employer details refresh without changing save time', () => {
  const saved = {a:store.snapshot(role,123)};
  store.reconcile(saved,[{...role,title:'Help Desk Technician'}]);
  assert.equal(saved.a.title,'Help Desk Technician');
  assert.equal(saved.a.savedAt,123);
});
test('invalid storage is handled and unsafe application URLs are rejected', () => {
  for (const raw of ['broken','[]','null','{"a":false}']) assert.equal(Object.keys(store.parse(raw)).length,0);
  assert.equal(store.snapshot({...role,url:'javascript:alert(1)'}).url,'');
});
