#!/usr/bin/env node
'use strict';

/**
 * Predict2U SportyBet collector.
 * Public JSON: /api/{country}/factsCenter/pcUpcomingEvents
 * Markets: 1X2, Double Chance, DNB, Over/Under, Home/Away O/U, GG/NG.
 */

const COUNTRY = String(process.env.SPORTYBET_COUNTRY || 'gh').replace(/[^a-z]/gi, '').toLowerCase() || 'gh';
const BASE = String(process.env.SPORTYBET_BASE || 'https://www.sportybet.com').replace(/\/+$/, '');
const SPORT = 'sr:sport:1';
const MARKETS = process.env.SPORTYBET_MARKETS || '1,10,11,18,19,20,29,60000,60010,60011,60012';
const PAGE = Math.max(20, Math.min(100, Number(process.env.SPORTYBET_PAGE_SIZE || 100)));
const TIMELINE = Math.max(12, Number(process.env.SPORTYBET_TIMELINE || 168));
const ZONE = process.env.APP_TIMEZONE || 'Africa/Accra';
const TIMEOUT = Number(process.env.SPORTYBET_TIMEOUT_MS || 20000);
const RETRIES = Number(process.env.SPORTYBET_RETRIES || 3);
const PAGE_PAUSE = Number(process.env.SPORTYBET_PAGE_PAUSE_MS || 120);

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function headers() {
  return {
    Accept: 'application/json, text/plain, */*',
    Origin: BASE,
    Referer: `${BASE}/${COUNTRY}/sport/football/today`,
    Clientid: 'web',
    Platform: 'web',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
  };
}

function odd(v) {
  const n = Number(v);
  return Number.isFinite(n) && n > 1.001 && n < 1000 ? Number(n.toFixed(3)) : null;
}

function nid(raw) {
  const m = String(raw ?? '').match(/(\d+)$/);
  return m ? Number(m[1]) : null;
}

function iso(ms) {
  return Number.isFinite(Number(ms)) ? new Date(Number(ms)).toISOString() : null;
}

function accraDate(ms) {
  if (!Number.isFinite(Number(ms))) return '';
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(new Date(Number(ms)));
}

async function fetchJson(url, attempt = 0) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT);
  try {
    const res = await fetch(url, { headers: headers(), signal: controller.signal });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      const error = new Error(`${res.status} ${res.statusText}`);
      error.status = res.status;
      error.body = body;
      throw error;
    }
    return body;
  } catch (error) {
    if (attempt < RETRIES && (error.name === 'AbortError' || error.status === 429 || Number(error.status) >= 500)) {
      const delay = Math.min(20000, 800 * (2 ** attempt)) + Math.floor(Math.random() * 400);
      console.warn(`SportyBet retry ${attempt + 1} in ${delay}ms: ${error.message}`);
      await sleep(delay);
      return fetchJson(url, attempt + 1);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function call(path, params = {}) {
  const url = new URL(`${BASE}${path}`);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
  }
  const body = await fetchJson(url);
  if (body?.bizCode !== 10000) {
    throw new Error(`SportyBet ${path} blocked: ${body?.innerMsg || body?.message || body?.bizCode}`);
  }
  return body.data;
}

function specifierTotal(market) {
  const spec = String(market?.specifier || market?.specifiers || '');
  const m = spec.match(/total=([0-9]+(?:\.[0-9]+)?)/i);
  return m ? m[1] : null;
}

function outcomePrice(outcomes, testers) {
  for (const o of outcomes || []) {
    const desc = String(o?.desc || o?.name || '').trim().toLowerCase();
    if (testers.some(fn => fn(desc))) {
      const price = odd(o?.odds ?? o?.odd ?? o?.price);
      if (price) return price;
    }
  }
  return null;
}

function lineKey(side, total) {
  if (total == null) return null;
  const n = Number(total);
  if (!Number.isFinite(n)) return null;
  const compact = String(n).replace('.', '');
  return `${side}${compact}`;
}

function parseSportyMarkets(markets) {
  const odds = {};
  const set = (key, value) => {
    const price = odd(value);
    if (price && odds[key] == null) odds[key] = price;
  };

  for (const market of markets || []) {
    const id = String(market?.id ?? '');
    const name = String(market?.name || market?.desc || '');
    const outs = market?.outcomes || [];
    const total = specifierTotal(market);

    if (id === '1' || /^1x2$/i.test(name)) {
      set('home', outcomePrice(outs, [d => d === 'home' || d === '1']));
      set('draw', outcomePrice(outs, [d => d === 'draw' || d === 'x']));
      set('away', outcomePrice(outs, [d => d === 'away' || d === '2']));
      if (odds.home) set('1', odds.home);
      if (odds.draw) set('X', odds.draw);
      if (odds.away) set('2', odds.away);
      continue;
    }

    if (id === '10' || /double chance/i.test(name)) {
      set('dc1x', outcomePrice(outs, [d => d.includes('home or draw') || d === '1x']));
      set('dc12', outcomePrice(outs, [d => d.includes('home or away') || d === '12' || d.includes('no draw')]));
      set('dcx2', outcomePrice(outs, [d => d.includes('draw or away') || d === 'x2']));
      if (odds.dc1x) set('1X', odds.dc1x);
      if (odds.dc12) set('12', odds.dc12);
      if (odds.dcx2) set('X2', odds.dcx2);
      continue;
    }

    if (id === '11' || /draw no bet/i.test(name)) {
      set('homeDnb', outcomePrice(outs, [d => d === 'home' || d === '1']));
      set('awayDnb', outcomePrice(outs, [d => d === 'away' || d === '2']));
      continue;
    }

    if (id === '29' || /gg\/ng/i.test(name) || /both teams/i.test(name)) {
      set('bttsYes', outcomePrice(outs, [d => d === 'yes' || d === 'gg']));
      set('bttsNo', outcomePrice(outs, [d => d === 'no' || d === 'ng']));
      if (odds.bttsYes) set('GG', odds.bttsYes);
      if (odds.bttsNo) set('NG', odds.bttsNo);
      continue;
    }

    if (id === '18' || /^over\/under$/i.test(name)) {
      const over = outcomePrice(outs, [d => d.startsWith('over')]);
      const under = outcomePrice(outs, [d => d.startsWith('under')]);
      const overKey = lineKey('over', total);
      const underKey = lineKey('under', total);
      if (overKey) set(overKey, over);
      if (underKey) set(underKey, under);
      continue;
    }

    if (id === '19' || /home o\/u/i.test(name) || /home team/i.test(name)) {
      const over = outcomePrice(outs, [d => d.startsWith('over')]);
      const under = outcomePrice(outs, [d => d.startsWith('under')]);
      if (total === '0.5') {
        set('homeOver05', over);
        set('homeUnder05', under);
      }
      continue;
    }

    if (id === '20' || /away o\/u/i.test(name) || /away team/i.test(name)) {
      const over = outcomePrice(outs, [d => d.startsWith('over')]);
      const under = outcomePrice(outs, [d => d.startsWith('under')]);
      if (total === '0.5') {
        set('awayOver05', over);
        set('awayUnder05', under);
      }
      continue;
    }

    if (id === '60011' || /1st half.*over\/under|first half.*o\/u/i.test(name)) {
      const over = outcomePrice(outs, [d => d.startsWith('over')]);
      const under = outcomePrice(outs, [d => d.startsWith('under')]);
      if (total === '0.5') set('fhOver05', over);
      if (total === '1.5') set('fhUnder15', under);
    }
  }

  return odds;
}

function eventRow(ev, tournament = {}) {
  const sport = ev?.sport || {};
  const category = sport?.category || {};
  const tour = category?.tournament || tournament || {};
  const kick = iso(ev?.estimateStartTime);
  const odds = parseSportyMarkets(ev?.markets);
  return {
    eventId: ev?.eventId || null,
    gameId: ev?.gameId || null,
    home: ev?.homeTeamName || '',
    away: ev?.awayTeamName || '',
    homeId: nid(ev?.homeTeamId),
    awayId: nid(ev?.awayTeamId),
    league: tour?.name || tournament?.name || '',
    country: category?.name || tournament?.categoryName || '',
    kickoff: kick,
    matchDate: accraDate(ev?.estimateStartTime),
    status: ev?.matchStatus || '',
    odds
  };
}

function flattenPage(data) {
  const out = [];
  for (const tour of data?.tournaments || []) {
    for (const ev of tour?.events || []) out.push(eventRow(ev, tour));
  }
  return out;
}

async function fetchPage(pageNum, timeline) {
  return call(`/api/${COUNTRY}/factsCenter/pcUpcomingEvents`, {
    sportId: SPORT,
    marketId: MARKETS,
    pageSize: PAGE,
    pageNum,
    timeline
  });
}

async function sportyUpcoming({ timeline = TIMELINE, force = false } = {}) {
  const first = await fetchPage(1, timeline);
  const total = Number(first?.totalNum || 0);
  const rows = flattenPage(first);
  const pages = Math.max(1, Math.ceil(total / PAGE));
  for (let page = 2; page <= pages; page += 1) {
    await sleep(PAGE_PAUSE);
    rows.push(...flattenPage(await fetchPage(page, timeline)));
  }
  console.log(`SportyBet feed: ${rows.length} football events (timeline ${timeline}h, ${COUNTRY})`);
  return { rows, total, timeline, country: COUNTRY };
}

module.exports = {
  COUNTRY,
  TIMELINE,
  parseSportyMarkets,
  eventRow,
  sportyUpcoming,
  accraDate,
  odd
};

if (require.main === module) {
  sportyUpcoming().then(pack => {
    const priced = pack.rows.filter(r => Object.keys(r.odds || {}).length).length;
    console.log(`Priced events: ${priced}/${pack.rows.length}`);
    const sample = pack.rows.find(r => r.odds && r.odds.home && r.odds.over25);
    if (sample) console.log(`Sample ${sample.home} vs ${sample.away} 1=${sample.odds.home} O2.5=${sample.odds.over25} 1X=${sample.odds.dc1x || '—'}`);
  }).catch(error => {
    console.error(error && error.stack ? error.stack : error);
    process.exit(1);
  });
}
