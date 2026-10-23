const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const data = JSON.parse(fs.readFileSync('public/organization-data.json','utf8'));
const customers = JSON.parse(fs.readFileSync('public/tencent-data.json','utf8')).rows.slice(1);
test('organization evidence belongs to a current customer and has a public source', () => {
  const ids = new Set();
  for (const record of data.customers) {
    assert.ok(customers.some(([id]) => id === record.id));
    assert.ok(!ids.has(record.id));ids.add(record.id);
    if (record.nodes.length) {
      assert.equal(new URL(record.source.url).protocol, 'https:');
      assert.match(record.checkedAt, /^\d{4}-\d{2}-\d{2}$/);
      assert.ok(record.source.publishedAt);
      function validate(nodes) { for(const node of nodes) {assert.ok(node.name.trim());if(node.children) validate(node.children);} }
      validate(record.nodes);
    } else assert.ok(record.note.includes('核实'));
  }
});
