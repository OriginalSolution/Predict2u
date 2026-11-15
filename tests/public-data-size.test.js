/* current-data.js must stay under the 9 MB release gate: past rows lose their per-match analysis. */
'use strict';
const assert = require('assert');
const { slimPastRows, SIZE_BUDGET } = require('../build-public-data.js');

const rows = [
  { home: 'A', away: 'B', matchDate: '2026-11-14', peerIntel: { version: 'peer-v292', tips: [] }, homeStreaks: { w: 3 } },
  { home: 'C', away: 'D', matchDate: '2026-11-15', peerIntel: { version: 'peer-v292', tips: [{ note: 'x' }] }, homeStreaks: { w: 1 } },
];
const out = slimPastRows(rows, '2026-11-15');
assert.strictEqual(out.pastRows, 1);
assert.strictEqual(out.droppedPeerIntel, 1);
assert.strictEqual(rows[0].peerIntel, undefined, 'past row keeps no peerIntel');
assert.deepStrictEqual(rows[0].homeStreaks, { w: 3 }, 'small bundle keeps past streaks');
assert.ok(rows[1].peerIntel && rows[1].peerIntel.tips.length, 'today and future keep peerIntel (SMT tips)');

// Over budget: tier 2 drops past heavy blocks, never today's.
const big = 'x'.repeat(Math.ceil(SIZE_BUDGET) + 10);
const rows2 = [
  { matchDate: '2026-11-10', homeStreaks: { pad: big }, awayProfile: { a: 1 } },
  { matchDate: '2026-11-16', homeStreaks: { w: 2 } },
];
const out2 = slimPastRows(rows2, '2026-11-15');
assert.ok(out2.droppedHeavy >= 2);
assert.strictEqual(rows2[0].homeStreaks, undefined);
assert.deepStrictEqual(rows2[1].homeStreaks, { w: 2 });
console.log('public-data-size test passed');
