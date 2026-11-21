/* current-data.js must stay under the 9 MB release gate. */
'use strict';
const assert = require('assert');
const vm = require('vm');
const {
  slimPublicRows,
  slimToBudget,
  compactOdds,
  compactPeerIntel,
  leanPastRow,
  publicFrom,
  publicTo,
  weekStartIso,
  serializeBundle,
  SIZE_BUDGET,
  HARD_LIMIT,
  ODDS_CANON_TO_ALIAS
} = require('../build-public-data.js');

assert.strictEqual(weekStartIso('2026-11-21'), '2026-11-16', 'Saturday week starts Monday');
assert.strictEqual(weekStartIso('2026-11-16'), '2026-11-16', 'Monday week starts itself');
assert.strictEqual(weekStartIso('2026-11-22'), '2026-11-16', 'Sunday week starts Monday');
assert.strictEqual(publicFrom('2026-11-21'), '2026-11-16', 'Saturday keeps this week plus yesterday is later than Monday');
assert.strictEqual(publicFrom('2026-11-16'), '2026-11-15', 'Monday still keeps yesterday so the live window is not empty of prior-day results');
assert.strictEqual(publicTo('2026-11-21'), '2026-11-28');
assert.ok(SIZE_BUDGET < HARD_LIMIT);
assert.strictEqual(HARD_LIMIT, 9 * 1024 * 1024);

const odds = compactOdds({ '1': 1.41, home: 1.41, X: 4.5, draw: 4.5, '2': 7.4, away: 7.4, GG: 1.92, bttsYes: 1.92, over25: 1.4326 });
assert.deepStrictEqual(odds, { home: 1.41, draw: 4.5, away: 7.4, bttsYes: 1.92, over25: 1.43 });
assert.strictEqual(odds['1'], undefined);

const intel = compactPeerIntel({
  version: 'peer-v292',
  class: 'similar',
  similar: true,
  rankGap: null,
  leagueSize: null,
  home: { sample: 4, win: 0.5, draw: null },
  away: { sample: 0, win: null },
  tips: [{
    id: 'OVER15',
    market: 'Over 1.5 Goals',
    settle: 'Over 1.5 Goals',
    evidence: [
      { d: '2026-08-22', team: 'A', opp: 'B', hit: true, line: 'long reconstructable line', meaning: '2 goals', leagueSize: null },
      { d: '2026-08-21', team: 'C', opp: 'D', hit: false, line: 'miss line', meaning: '1 goal' }
    ]
  }],
  notes: ['thin sample']
});
assert.strictEqual(intel.rankGap, undefined);
assert.strictEqual(intel.home.draw, undefined);
assert.strictEqual(intel.tips[0].settle, 'Over 1.5 Goals', 'settle is used by Matchup Lab add-to-slip');
assert.strictEqual(intel.tips[0].evidence[0].line, undefined, 'evidence.line is reconstructed on the page');
assert.strictEqual(intel.tips[0].evidence[0].meaning, '2 goals');
assert.strictEqual(intel.tips[0].evidence[1].hit, false, 'misses must keep hit:false');
assert.deepStrictEqual(intel.notes, ['thin sample']);

const past = leanPastRow({
  id: 'sr:match:1',
  home: 'A',
  away: 'B',
  league: 'L',
  matchDate: '2026-11-16',
  kickoff: '2026-11-16T15:00:00Z',
  status: 'NS',
  odds: { home: 1.5, '1': 1.5, draw: 4, over25: 1.8 },
  peerIntel: { tips: [{ id: 'X' }] },
  homeStreaks: { w: 3 },
  homeWinRate: 0.4,
  leagueId: null,
  analysisPending: true
});
assert.strictEqual(past.peerIntel, undefined);
assert.strictEqual(past.homeStreaks, undefined);
assert.strictEqual(past.homeWinRate, undefined);
assert.strictEqual(past.analysisPending, undefined);
assert.strictEqual(past.leagueId, undefined);
assert.strictEqual(past.home, 'A');
assert.strictEqual(past.odds.home, 1.5);
assert.strictEqual(past.odds['1'], undefined);
assert.strictEqual(past.odds.over25, undefined, 'past rows keep only 1X2 odds');

const rows = [
  { home: 'A', away: 'B', matchDate: '2026-11-14', peerIntel: { version: 'peer-v292', tips: [] }, homeStreaks: { w: 3 }, odds: { home: 1.2, '1': 1.2 } },
  { home: 'C', away: 'D', matchDate: '2026-11-16', peerIntel: { version: 'peer-v292', tips: [] }, homeStreaks: { w: 1 }, leagueId: null },
  { home: 'E', away: 'F', matchDate: '2026-11-21', peerIntel: { version: 'peer-v292', tips: [{ id: 'OVER15', evidence: [{ line: 'x', hit: true }] }] }, id: 'sr:1', sportyEventId: 'sr:1', odds: { home: 1.8, '1': 1.8, over25: 1.9 }, leagueId: null, analysisPending: false }
];
const { rows: slimmed, stats } = slimPublicRows(rows, '2026-11-21', { keepPastFrom: '2026-11-16' });
assert.strictEqual(stats.droppedOldPast, 1, 'pre-Monday stale rows drop when keepPastFrom is set');
assert.strictEqual(slimmed.length, 2);
assert.strictEqual(slimmed[0].peerIntel, undefined, 'remaining past rows are lean');
assert.strictEqual(slimmed[0].homeStreaks, undefined);
assert.ok(slimmed[1].peerIntel && slimmed[1].peerIntel.tips[0].id === 'OVER15', 'today keeps tips');
assert.strictEqual(slimmed[1].peerIntel.tips[0].evidence[0].line, undefined);
assert.strictEqual(slimmed[1].sportyEventId, undefined, 'duplicate sportyEventId is dropped');
assert.strictEqual(slimmed[1].leagueId, undefined, 'null fields are omitted');
assert.strictEqual(slimmed[1].odds['1'], undefined);
assert.strictEqual(slimmed[1].odds.home, 1.8);

const meta = { version: 'v288', today: '2026-11-21' };
const body = serializeBundle(meta, '2026-11-21T00:00:00Z', null, slimmed);
assert.ok(body.includes('window.MATCHES='));
assert.ok(body.includes('o[A[k]]=o[k]'), 'odds hydrator is appended');
const sandbox = { window: {} };
vm.runInNewContext(body, sandbox);
assert.strictEqual(sandbox.window.MATCHES[1].odds.home, 1.8);
assert.strictEqual(sandbox.window.MATCHES[1].odds['1'], 1.8, 'hydrator restores numeric 1/X/2 aliases');
assert.strictEqual(sandbox.window.MATCHES[1].odds.over25, 1.9);
for (const [canon, alias] of Object.entries(ODDS_CANON_TO_ALIAS)) {
  if (sandbox.window.MATCHES[1].odds[canon] != null) {
    assert.strictEqual(sandbox.window.MATCHES[1].odds[alias], sandbox.window.MATCHES[1].odds[canon], `alias ${alias}`);
  }
}

// Budget guard: a bloated past row is leaned / dropped rather than blowing the 9 MB gate.
const pad = 'x'.repeat(200);
const bloated = [];
for (let i = 0; i < 40; i++) {
  bloated.push({
    matchDate: '2026-11-16',
    home: 'H' + i,
    away: 'A' + i,
    peerIntel: { notes: [pad], tips: [{ evidence: [{ line: pad, meaning: pad, hit: true }] }] },
    homeStreaks: { pad },
    odds: { home: 1.2, '1': 1.2 }
  });
}
bloated.push({ matchDate: '2026-11-21', home: 'Today', away: 'Side', odds: { home: 1.4, '1': 1.4 }, peerIntel: { version: 'peer-v292', tips: [{ id: 'HOME_WIN', evidence: [{ line: 'keep-me-id', hit: true, d: '2026-08-01' }] }] } });
const guarded = slimToBudget(bloated, '2026-11-21', { version: 'test' }, 't', null);
assert.ok(guarded.stats.bytes <= SIZE_BUDGET, `slimmed bundle ${guarded.stats.bytes} must be <= ${SIZE_BUDGET}`);
assert.ok(guarded.rows.some(r => r.home === 'Today'), 'today is never dropped');
const todayRow = guarded.rows.find(r => r.home === 'Today');
assert.strictEqual(todayRow.peerIntel.tips[0].id, 'HOME_WIN');

console.log('public-data-size test passed');
