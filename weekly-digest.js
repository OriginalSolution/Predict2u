/* PREDICT2U — WEEKLY DIGEST
   Sunday email: your slips this week, wins AND losses, your record.
   Opt-in via profiles.email_digest (default true). One-click unsubscribe.
   Losses are always included — the honesty rule applies to emails too. */
const SUPA_URL=process.env.SUPABASE_URL||"", SECRET=process.env.SUPABASE_SECRET_KEY||"", RESEND=process.env.RESEND_API_KEY||"";
if(!SUPA_URL||!SECRET){ console.error("Missing Supabase env"); process.exit(1); }
if(!RESEND){ console.log("No RESEND_API_KEY — nothing to send."); process.exit(0); }
const H={apikey:SECRET,Authorization:"Bearer "+SECRET,"Content-Type":"application/json"};
const get=async q=>{ const r=await fetch(`${SUPA_URL}/rest/v1/${q}`,{headers:H});
  if(!r.ok) throw new Error(`${q} -> ${r.status}`); return r.json(); };
const patch=async(q,b)=>fetch(`${SUPA_URL}/rest/v1/${q}`,{method:"PATCH",headers:{...H,Prefer:"return=minimal"},body:JSON.stringify(b)});

// Predict2U picks record for the week (from the committed picks-history.json — no API calls)
let P2U_WEEK="";
try{ const f=require("./picks-media.js"); let w=0,l=0;
  for(let i=1;i<=7;i++){ const d=new Date(Date.parse(f.TODAY+"T12:00:00Z")-i*864e5).toISOString().slice(0,10); const r=f.record(f.settledOn(d)); w+=r.w; l+=r.l; }
  if(w+l) P2U_WEEK=`<tr><td style="color:#8fa093;font-size:14px;border-top:1px solid #1b2a1c;padding-top:16px">Predict2U picks this week: <b style="color:#7ede8f">${w}W</b> – <b style="color:#e07a7a">${l}L</b> (${Math.round(100*w/(w+l))}%) · <a href="https://predict2u.com/bankers.html" style="color:#3ecf6e">today's slips</a></td></tr>`;
  console.log("Picks week record:", w+"W", l+"L");
}catch(e){ console.log("picks week record skipped:", e.message); }

(async()=>{
  const since=new Date(Date.now()-7*864e5).toISOString();
  const profs=await get("profiles?email_digest=eq.true&select=id,handle");
  console.log(`${profs.length} opted-in profiles.`);
  for(const p of profs){
    const slips=await get(`slips?user_id=eq.${p.id}&is_public=eq.true&settled_at=gte.${since}&select=status,stake,combined_odds`);
    if(!slips.length){ console.log(`@${p.handle}: nothing settled this week — no email.`); continue; }
    const w=slips.filter(s=>s.status==="won").length, l=slips.filter(s=>s.status==="lost").length;
    if(w+l===0){ console.log(`@${p.handle}: only voids — no email.`); continue; }
    const units=slips.reduce((a,s)=>a+(s.status==="won"?s.stake*((s.combined_odds||1)-1):s.status==="lost"?-s.stake:0),0);
    const rec=await get(`user_ranks?user_id=eq.${p.id}&select=hit_pct,rank_tier,verified,slips_won`);
    const r=rec[0]||{};
    const email=await authEmail(p.id);
    if(!email){ console.log(`@${p.handle}: no email.`); continue; }
    const pct=Math.round(100*w/(w+l));
    const sign=units>=0?"+":"";
    const html=`
<table width="100%" cellpadding="0" cellspacing="0" style="background:#070d08;padding:32px 0;font-family:Arial,Helvetica,sans-serif">
 <tr><td align="center"><table width="440" cellpadding="0" cellspacing="0" style="background:#0d150e;border:1px solid #1b2a1c;border-radius:16px;padding:32px">
  <tr><td align="center" style="padding-bottom:26px"><img src="https://predict2u.com/email-logo.png" alt="Predict2u" width="300" style="display:block;width:300px;max-width:100%;height:auto;border:0"/></td></tr>
  <tr><td style="color:#f2f7f0;font-size:20px;font-weight:700;padding-bottom:6px">Your week, @${p.handle}</td></tr>
  <tr><td style="color:#8fa093;font-size:15px;line-height:22px;padding-bottom:20px">Every settled slip, wins and losses.</td></tr>
  <tr><td align="center" style="padding-bottom:8px">
    <span style="color:#7ede8f;font-size:44px;font-weight:900">${w}W</span>
    <span style="color:#5c6f5f;font-size:30px;font-weight:900"> – </span>
    <span style="color:#e07a7a;font-size:44px;font-weight:900">${l}L</span></td></tr>
  <tr><td align="center" style="color:#8fa093;font-size:14px;padding-bottom:20px">${pct}% this week · ${sign}${units.toFixed(2)} units</td></tr>
  ${r.hit_pct!=null?`<tr><td style="color:#8fa093;font-size:14px;border-top:1px solid #1b2a1c;padding-top:16px">All-time: <b style="color:#f2f7f0">${r.hit_pct}%</b> over ${r.slips_won||0} wins${r.rank_tier?` · rank <b style="color:#f2f7f0">${r.rank_tier}</b>`:""}${r.verified?' · <span style="color:#3ecf6e">verified</span>':""}</td></tr>`:""}
  ${P2U_WEEK}
  <tr><td align="center" style="padding:22px 0">
    <a href="https://predict2u.com/community.html" style="background:#3ecf6e;color:#06120a;font-size:15px;font-weight:800;text-decoration:none;padding:14px 32px;border-radius:10px;display:inline-block">See your record</a></td></tr>
  <tr><td style="color:#5c6f5f;font-size:12px;line-height:18px;border-top:1px solid #1b2a1c;padding-top:18px">
    18+ only. <a href="https://predict2u.com/community.html" style="color:#5c6f5f">Turn these emails off</a> · predict2u.com</td></tr>
 </table></td></tr></table>`;
    const res=await fetch("https://api.resend.com/emails",{method:"POST",
      headers:{Authorization:"Bearer "+RESEND,"Content-Type":"application/json"},
      body:JSON.stringify({from:"Predict2u <noreply@predict2u.com>",to:[email],subject:`Your week: ${w}W–${l}L`,html})});
    if(res.ok){ console.log(`Digest sent to @${p.handle} (${w}W-${l}L).`); await patch(`profiles?id=eq.${p.id}`,{last_digest_at:new Date().toISOString()}); }
    else console.error(`@${p.handle}: ${await res.text()}`);
  }
})().catch(e=>{ console.error("Digest failed:",e.message); process.exit(1); });

async function authEmail(id){ const r=await fetch(`${SUPA_URL}/auth/v1/admin/users/${id}`,{headers:H});
  if(!r.ok) return null; const j=await r.json(); return j.email||null; }
