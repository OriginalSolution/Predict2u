/* ============================================================
   POST-SOCIAL — Telegram channel automation for Predict2u
   ------------------------------------------------------------
   Runs daily at 00:50 UTC (after the email workflows commit the
   fresh today*.png / results.png). Posts up to three messages:
     1. YESTERDAY'S RESULTS — honest W-L record with results.png.
        Wins AND losses, always. Skipped only if nothing settled.
     2. TODAY'S PICKS — teaser caption with today.png. Skipped
        honestly when the board has no bankers.
     3. SUNDAYS ONLY — 7-day record recap (text post).
   Captions are also written to social-captions.txt so the same
   text can be copy-forwarded to the WhatsApp Channel in seconds.
   Secrets required: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
   DRY_RUN=1 prints everything instead of posting (safe testing).
   ============================================================ */
const fs = require("fs");
const path = require("path");
const HERE = __dirname;

const TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const CHAT  = process.env.TELEGRAM_CHAT_ID || "";
const DRY   = process.env.DRY_RUN === "1" || !TOKEN || !CHAT;

const SITE = "predict2u.com";
const RG   = "18+ | Bet responsibly. Never stake what you can't afford to lose.";

/* ---------- load the bot picks feed (picks.json + picks-history.json) ---------- */
const feed = require("./bot-feed-media.js");
const dstr = d => d.toISOString().slice(0, 10);
const today = new Date();
const TODAY = feed.TODAY, YDAY = feed.YDAY;
const settledOn = date => feed.settledOn(date);
const record = list => feed.record(list);

/* ---------- captions ---------- */
const esc = t => String(t); // Telegram plain-text captions — no parse_mode, nothing to escape
const messages = []; // { photo: filename|null, caption }

// 1) RESULTS — the honesty-first post. Losses are never hidden.
const yr = record(settledOn(YDAY));
if (yr.n > 0) {
  const tone = yr.pct >= 70 ? "Strong board." : yr.pct >= 50 ? "Mixed board — posted anyway. Every result counts here." : "Rough board. We post the losses too — that's the whole point.";
  messages.push({
    photo: ["social-results.png","results.png"].find(f => fs.existsSync(path.join(HERE, f))) || null,
    caption: `YESTERDAY'S RESULTS — ${YDAY}\n\n${yr.w} WON  •  ${yr.l} LOST  (${yr.pct}%)\n${tone}\n\nEvery slip and result: ${SITE}/bankers.html\n\n${RG}`
  });
}

// 2) TODAY'S PICKS — bot slips with SportyBet codes, drive to the site.
const todaysPicks = feed.picksOn(TODAY);
const todaysSlips = feed.slipsOn(TODAY);
const todayImg = ["social-today.png", "today.png", "acca-1.png"].find(f => fs.existsSync(path.join(HERE, f)));
if (todaysPicks.length) {
  const bots = [...new Set(todaysSlips.map(s => s.bot))].join(" + ");
  const codes = todaysSlips.filter(s => s.code).slice(0, 6).map(s => `${s.code} (${s.bot}, ${s.legs.filter(x => x.date === TODAY).length} legs)`).join("\n");
  messages.push({
    photo: todayImg || null,
    caption: `TODAY'S BOT PICKS — ${TODAY}\n\n${todaysPicks.length} picks in ${todaysSlips.length} SportyBet slips from ${bots}.\n\nSportyBet codes:\n${codes}\n\nLoad a code at sportybet.com/gh or see every slip: ${SITE}/bankers.html\n\n${RG}`
  });
} else {
  console.log("No bot picks for today — honest skip, no picks post.");
}

// 3) SUNDAY — 7-day recap.
if (today.getUTCDay() === 0) {
  let w = 0, l = 0;
  for (let i = 1; i <= 7; i++) {
    const d = dstr(new Date(today.getTime() - i * 86400000));
    const r = record(settledOn(d)); w += r.w; l += r.l;
  }
  if (w + l > 0) {
    const pct = Math.round(100 * w / (w + l));
    messages.push({
      photo: null,
      caption: `THE WEEK, IN FULL — last 7 days\n\n${w} WON  •  ${l} LOST  (${pct}%)\n\nEvery result posted daily, wins and losses. That's the record — check it yourself: ${SITE}\n\n${RG}`
    });
  }
}

/* ---------- write the WhatsApp copy-forward file ---------- */
fs.writeFileSync(path.join(HERE, "social-captions.txt"),
  messages.map(m => m.caption).join("\n\n==============================\n\n") || "Nothing to post today.");

/* ---------- post to Telegram ---------- */
async function send(m) {
  if (DRY) { console.log("---- DRY RUN ----\nphoto:", m.photo, "\n" + m.caption + "\n"); return; }
  const url = `https://api.telegram.org/bot${TOKEN}/` + (m.photo ? "sendPhoto" : "sendMessage");
  const form = new FormData();
  form.append("chat_id", CHAT);
  if (m.photo) {
    form.append("photo", new Blob([fs.readFileSync(path.join(HERE, m.photo))]), m.photo);
    form.append("caption", m.caption.slice(0, 1024)); // Telegram caption limit
  } else {
    form.append("text", m.caption.slice(0, 4096));
  }
  const res = await fetch(url, { method: "POST", body: form });
  const j = await res.json().catch(() => ({}));
  if (!j.ok) console.error("Telegram error:", JSON.stringify(j).slice(0, 300));
  else console.log("Posted:", m.photo || "text post");
}

(async () => {
  if (!messages.length) { console.log("Nothing to post today."); return; }
  for (const m of messages) { await send(m); await new Promise(r => setTimeout(r, 1500)); }
  console.log(`Done — ${messages.length} message(s) ${DRY ? "(dry run)" : "posted"}.`);
})();
