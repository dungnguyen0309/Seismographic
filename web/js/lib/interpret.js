// Port of prm/interpret.py: plain-language readings of the index, and what to do with them.
import { fixed, signed, countdown, ordinal } from "./format.js";
import { asMap, asRows, na, redFlags } from "./scoring.js";

// Text tables, written from prm/interpret.py
export const AUDIENCES = {
  "business": "Business & investors",
  "ngo": "NGOs & humanitarian work",
  "travel": "Travel, study & staff safety",
  "research": "Policy, journalism & research"
};

export const TIER_MEANING = {
  "Low": [
    "Among the most stable places in the sample.",
    "Politics rarely disrupts daily life or business. Institutions generally work, disputes go through courts and elections, and the economy has buffers. Risk comes mainly from unexpected shocks."
  ],
  "Moderate": [
    "Broadly functional, with specific weak spots.",
    "Most things work most of the time, but there are soft spots: a stretched budget, patchy governance or pockets of unrest. Disruptions happen, and are usually contained and short."
  ],
  "Elevated": [
    "Material risk on more than one front.",
    "Expect periodic protests, policy surprises or economic stress. Contracts and plans can be upset by events outside your control, so they need contingencies and regular review."
  ],
  "High": [
    "Serious, persistent risk.",
    "Instability, weak institutions and/or economic crisis are part of normal operating conditions. Working there takes active risk management: security planning, financial safeguards and local advice."
  ],
  "Severe": [
    "Among the most dangerous and fragile places in the world.",
    "War, the near-collapse of the state or a deep economic crisis. Daily life and business are heavily disrupted; outside presence is often limited to essential humanitarian, diplomatic or security work."
  ]
};

export const PILLAR_MEANING = {
  "stability": {
    "ground": "Political violence, unrest and armed conflict: protests that shut roads and shops, attacks, curfews and, at the extreme, war.",
    "felt_by": "Everyone who is there (residents, staff and travellers) and anything with a fixed location."
  },
  "governance": {
    "ground": "Institutions you can't rely on: slow or biased courts, demands for bribes, rules that change without warning, weak protection of property and contracts.",
    "felt_by": "Businesses, investors and NGOs dealing with officials, permits, contracts or courts."
  },
  "economic": {
    "ground": "Exposure to an economic crisis: prices rising fast, a falling currency, shortages of dollars, tax rises or spending cuts, and payments that arrive late or not at all.",
    "felt_by": "Anyone who earns, saves, borrows or trades in the local currency, importers most of all."
  },
  "social": {
    "ground": "Pressures that can turn into instability: jobless young people, cost-of-living anger and mass displacement.",
    "felt_by": "Communities, employers and governments. These pressures often signal unrest to come."
  }
};

export const INDICATOR_PHRASE = {
  "wgi_pv": "a high perceived risk of political violence",
  "battle_deaths_100k": "deaths in armed conflict",
  "homicide": "violent crime",
  "wgi_va": "limited political freedoms and accountability",
  "wgi_ge": "weak public services and policy delivery",
  "wgi_rq": "a difficult regulatory environment",
  "wgi_rl": "weak rule of law (courts, contracts, property)",
  "wgi_cc": "corruption",
  "inflation": "high inflation",
  "gdp_growth": "weak growth",
  "gov_debt": "heavy public debt",
  "fiscal_balance": "a large budget deficit",
  "current_account": "a large external deficit",
  "reserves_months": "thin foreign-exchange reserves",
  "unemployment": "unemployment",
  "youth_unemployment": "youth unemployment",
  "displaced_share": "mass displacement"
};

export const FLAG_MEANING = {
  "battle_deaths_raw": [
    "Armed conflict is killing people on a scale that counts as war or active conflict. Fighting can move fast, cut roads and supply lines, and spill into neighbouring areas.",
    "Most governments advise against travel to affected areas; organisations limit presence to essential staff with security plans, and insurers treat the area as a war zone."
  ],
  "inflation": [
    "Prices are rising fast, so wages, savings and fixed-price contracts lose value month by month. Fast price rises often set off cost-of-living protests and strikes.",
    "Businesses index contracts to inflation or price them in hard currency, review salaries and cash transfers often, and buy stock before prices rise."
  ],
  "gdp_growth": [
    "The economy is shrinking: weaker demand, layoffs and falling tax revenue, which can sour the political mood and squeeze the government's budget.",
    "Firms cut sales forecasts, review the credit risk of local customers and prepare for layoffs and wage disputes."
  ],
  "gov_debt": [
    "Public debt is high, leaving little room to respond to a shock. Tax rises, spending cuts or an IMF programme become more likely, and in the worst case a debt restructuring.",
    "Investors check their exposure to government bonds and public-sector clients, and treat budget announcements and IMF talks as risk events."
  ],
  "fiscal_balance": [
    "The government spends far more than it collects. That usually ends in tax rises, spending cuts, money printing or late payments to suppliers.",
    "Suppliers tighten payment terms with government clients and plan for tax changes."
  ],
  "current_account": [
    "The country relies on foreign money to pay for its imports, which leaves the currency vulnerable if investors pull back.",
    "Firms hedge or reduce their currency exposure and review supply chains that depend on imports."
  ],
  "reserves_months": [
    "The central bank has little foreign currency left: less than three months of imports. Import restrictions, dollar shortages, capital controls or a devaluation often follow.",
    "Firms keep extra stock of imported inputs, convert local earnings to hard currency promptly, and check the rules on moving money out of the country."
  ],
  "youth_unemployment": [
    "A quarter or more of young people who want work can't find it. Youth unemployment is a well-documented driver of protest movements and emigration.",
    "Employers invest in local hiring and training; analysts watch campuses, social media and fuel or food price decisions as protest triggers."
  ],
  "displaced_share": [
    "At least one person in twenty has been forced from their home. Needs for shelter, food and health care are large, and neighbouring countries carry heavy pressure.",
    "Humanitarian agencies scale up through UN-led coordination; donors and host governments plan for long-term displacement as well as emergency relief."
  ],
  "homicide": [
    "Violent crime is high, at twenty or more murders per 100,000 people a year, and it affects residents, staff and visitors.",
    "Organisations adopt crime-specific security measures: vetted transport, secure accommodation, restrictions on night travel."
  ]
};

export const NEAR = {
  "inflation": [
    ">=",
    15
  ],
  "gdp_growth": [
    "<",
    1.0
  ],
  "gov_debt": [
    ">=",
    80
  ],
  "fiscal_balance": [
    "<=",
    -4
  ],
  "current_account": [
    "<=",
    -4
  ],
  "reserves_months": [
    "<",
    3.6
  ],
  "youth_unemployment": [
    ">=",
    20
  ],
  "displaced_share": [
    ">=",
    3
  ],
  "homicide": [
    ">=",
    15
  ],
  "battle_deaths_raw": [
    ">=",
    10
  ]
};

export const CAVEATS = [
  "Scores are relative: they show where a country sits among the others and give no probability of any event.",
  "The data look backwards: governance scores describe last year and conflict data lag by up to two years. Check current news and official travel advice.",
  "This is general, educational guidance. It is not investment, legal or security advice."
];


const NEAR_TEXT = {
  inflation: (v) => `Inflation is ${fixed(v, 1)}%, approaching the 20% warning line.`,
  gdp_growth: (v) => `Growth is only ${fixed(v, 1)}%, close to stalling.`,
  gov_debt: (v) => `Public debt is ${fixed(v, 0)}% of GDP, approaching the 90% warning line.`,
  fiscal_balance: (v) => `The budget deficit is ${fixed(-v, 1)}% of GDP, close to the 5% warning line.`,
  current_account: (v) => `The external deficit is ${fixed(-v, 1)}% of GDP, close to the 5% warning line.`,
  reserves_months: (v) => `Reserves cover ${fixed(v, 1)} months of imports, close to the 3-month warning line.`,
  youth_unemployment: (v) => `Youth unemployment is ${fixed(v, 0)}%, approaching the 25% warning line.`,
  displaced_share: (v) => `${fixed(v, 1)}% of the population is displaced, approaching the 5% warning line.`,
  homicide: (v) => `The homicide rate is ${fixed(v, 0)} per 100,000, approaching the warning line of 20.`,
  battle_deaths_raw: (v) => `UCDP recorded ${fixed(v, 0, { group: true })} battle deaths: below the 25 that define an active conflict, but more than none.`,
};

const COMPARE = { ">=": (a, b) => a >= b, "<": (a, b) => a < b, "<=": (a, b) => a <= b };
const DAY = 86400000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const dayOf = (iso) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
const dmy = (iso) => `${iso.slice(8, 10)} ${MONTHS[+iso.slice(5, 7) - 1]} ${iso.slice(0, 4)}`; // 16 Jan 2027

// ' (32.5%)', ' (69.3% of GDP)', ' (4.4 months of imports)' - or '' when there is no value
function shown(ind, raw) {
  if (na(raw)) return "";
  const n = fixed(raw, ind.decimals, { group: true });
  if (ind.unit === "% change") return ` (${n}%)`;
  return ` (${n}${ind.unit.startsWith("%") ? "" : " "}${ind.unit})`;
}

const todayIso = () => { // the visitor's calendar day, as dt.date.today() (toISOString would give the UTC day)
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// One country's numbers as a plain-language reading with practical actions (prm.interpret.Reading).
// table: the master table; events/flows: that country's rows (events: date, event, significance; flows: host, value);
// wgiTrend: {change, ...} from data/wgi_trend.json; today: "YYYY-MM-DD" (defaults to the clock).
export function countryReading(iso3, table, values, scores, hist, { events = null, flows = null, year, today = null, wgiTrend = null, config } = {}) {
  const cfg = config;
  const tab = asMap(table);
  const row = tab.get(iso3);
  const name = row.name;
  const v = asMap(values).get(iso3) ?? {};
  const s = asMap(scores).get(iso3) ?? {};
  const tier = typeof s.tier === "string" ? s.tier : null;
  const out = { iso3, name, tier, headline: "", ground: "", drivers: [], warnings: [], near: [], direction: [], events: [], actions: {}, caveats: [] };

  if (tier === null) {
    out.headline = `There is not enough data to score ${name}, so no reading can be made from the index.`;
    out.ground = "Use current news, official travel advice and specialist sources instead.";
    out.caveats = [...CAVEATS];
    return out;
  }

  // Headline
  let [summary, ground] = TIER_MEANING[tier];
  const peers = [...tab.values()].filter((r) => r.region === row.region && !na(r.composite)).sort((a, b) => b.composite - a.composite);
  const at = peers.findIndex((r) => r.iso3 === iso3);
  const regionPos = at >= 0 ? at + 1 : null;
  out.headline = `${name} is in the ${tier} tier (${fixed(s.composite, 0)}/100, ${ordinal(Math.trunc(s.rank))} riskiest of ${Math.trunc(s.n_ranked)}`
    + (regionPos ? `; ${ordinal(regionPos)} of ${peers.length} in ${row.region}` : "") + `). ${summary}`;

  // Drivers: the high-risk pillars (50+) and the indicators behind them
  const pillars = cfg.pillars.filter((p) => !na(s[p.key])).sort((a, b) => s[b.key] - s[a.key]);
  for (const p of pillars.filter((p) => s[p.key] >= 50).slice(0, 3)) {
    const inds = cfg.indicators.filter((i) => i.pillar === p.key && !na(s[`n_${i.key}`])).sort((a, b) => s[`n_${b.key}`] - s[`n_${a.key}`]);
    const evidence = inds.slice(0, 2).filter((i) => s[`n_${i.key}`] >= 60)
      .map((i) => `${INDICATOR_PHRASE[i.key] ?? i.short.toLowerCase()}${shown(i, v[i.key])}`);
    out.drivers.push({ pillar: p.key, label: p.label, score: s[p.key], ground: PILLAR_MEANING[p.key].ground, felt_by: PILLAR_MEANING[p.key].felt_by, evidence });
  }
  if (!out.drivers.length && pillars.length) {
    const weakest = pillars[0];
    ground += ` No pillar scores as high risk; the relatively weakest area is ${weakest.label} (${fixed(s[weakest.key], 0)}/100).`;
  }
  out.ground = ground;

  // Warning signs (red flags) and near misses
  const flags = Object.keys(v).length ? redFlags(v, cfg) : [];
  out.warnings = flags.filter((f) => FLAG_MEANING[f.key]).map((f) => ({ severity: f.severity, label: f.label, meaning: FLAG_MEANING[f.key][0], response: FLAG_MEANING[f.key][1] }));
  const flagged = new Set(flags.map((f) => f.key));
  for (const [key, [op, level]] of Object.entries(NEAR)) {
    const value = v[key];
    if (flagged.has(key) || na(value)) continue;
    if (key === "battle_deaths_raw" && value <= 0) continue;
    if (COMPARE[op](Number(value), level)) out.near.push(NEAR_TEXT[key](Number(value)));
  }

  // Direction
  const delta = row.delta_1y;
  if (!na(delta)) {
    const moved = typeof row.prev_tier === "string" && row.prev_tier !== tier ? ` and moved from the ${row.prev_tier} to the ${tier} tier` : "";
    const d = fixed(delta, 1, { sign: true });
    if (delta >= 3) out.direction.push(`Getting noticeably riskier: up ${d} points since ${year - 1}${moved}.`);
    else if (delta >= 1) out.direction.push(`Edging riskier: ${d} points since ${year - 1}${moved}.`);
    else if (delta <= -3) out.direction.push(`Getting noticeably safer: ${d} points since ${year - 1}${moved}.`);
    else if (delta <= -1) out.direction.push(`Edging safer: ${d} points since ${year - 1}${moved}.`);
    else out.direction.push(`Roughly flat since ${year - 1} (${signed(delta)} points).`);
  }
  const ch = asRows(hist).filter((r) => r.iso3 === iso3 && !na(r.composite)).sort((a, b) => a.year - b.year);
  if (ch.length >= 3) {
    const first = ch[0];
    const change = s.composite - first.composite;
    if (Math.abs(change) >= 5) out.direction.push(`Over the longer run it has ${change > 0 ? "risen" : "fallen"} from ${fixed(first.composite, 0)} in ${first.year} to ${fixed(s.composite, 0)} now.`);
    else out.direction.push(`Over the longer run it has been fairly stable (${fixed(first.composite, 0)} in ${first.year}, ${fixed(s.composite, 0)} now).`);
  }

  // Coming up
  const t0 = dayOf(today ?? todayIso());
  const upcoming = (events ? asRows(events) : []).filter((e) => e.iso3 === iso3 && dayOf(e.date) >= t0 && dayOf(e.date) <= t0 + 365 * DAY)
    .sort((a, b) => dayOf(a.date) - dayOf(b.date));
  out.events = upcoming.map((e) => `${e.event}, ${dmy(e.date)} (${countdown((dayOf(e.date) - t0) / DAY)}, ${e.significance} significance)`);
  const next = upcoming[0] ?? null;

  // What to do with it
  const hi = Object.fromEntries(cfg.pillars.map((p) => [p.key, !na(s[p.key]) && s[p.key] >= 60]));
  const conflict = flagged.has("battle_deaths_raw");
  const crime = flagged.has("homicide");
  const any = (...keys) => keys.some((k) => flagged.has(k));
  const money = any("inflation", "reserves_months", "current_account");
  const budget = any("gov_debt", "fiscal_balance");
  const displaced = v.displaced_share;
  const calm = s.composite < 30 && !flags.length && !(wgiTrend && wgiTrend.change <= -cfg.WGI_TREND_THRESHOLD);
  const when = next ? `'${next.event}' (${dmy(next.date)})` : null;

  const business = ["Use the score to decide where to look closer: compare with peers (Peers tab) and read the drivers before deciding anything."];
  if (hi.economic || money) business.push("Protect against currency and payment risk: price in hard currency or index to inflation, shorten payment terms, consider hedging, and check the rules on moving money out.");
  if (flagged.has("reserves_months")) business.push("Thin reserves often come before import limits or a devaluation: hold extra stock of imported inputs and convert local earnings promptly.");
  if (budget) business.push("Expect tax rises, spending cuts or late government payments: check your exposure to public-sector clients and contracts.");
  if (hi.governance) business.push("Raise due-diligence standards: vet partners and owners, enforce anti-bribery compliance, use international arbitration clauses, and consider political-risk insurance.");
  if (hi.stability || conflict) business.push("Plan for disruption: business-continuity and evacuation plans, security for staff and sites, and insurance that covers political violence.");
  if (hi.social) business.push("Look after labour and community relations: watch cost-of-living protests and strikes; local hiring and engagement reduce friction.");
  if (when) business.push(`Treat ${when} as a decision window: avoid locking in large, hard-to-reverse commitments just before it.`);
  if (calm) business.push("A relatively stable profile: standard due diligence is usually enough. Watch *Score changes* for early shifts.");

  const ngo = [];
  if (!na(displaced) && displaced >= 1) {
    let hosts = [];
    if (flows) {
      const names = new Map([...tab.values()].map((r) => [r.iso3, r.name]));
      hosts = asRows(flows).filter((f) => (f.origin === undefined || f.origin === iso3) && names.has(f.host))
        .map((f, i) => ({ ...f, i })).sort((a, b) => b.value - a.value || a.i - b.i).slice(0, 3).map((f) => names.get(f.host));
    }
    ngo.push(`About ${fixed(displaced, 1)}% of the population is displaced: plan for shelter, protection, food and health needs through UN-led coordination (OCHA, UNHCR).`
      + (hosts.length > 1 ? ` The largest numbers abroad are in ${hosts.slice(0, -1).join(", ")} and ${hosts[hosts.length - 1]}.`
        : hosts.length ? ` The largest number abroad is in ${hosts[0]}.` : ""));
  }
  if (conflict || hi.stability) ngo.push("Access and safety come first: negotiate access, apply humanitarian principles, and keep a security risk-management plan and duty of care for staff.");
  if (flagged.has("inflation")) ngo.push("Fast-rising prices erode the value of cash and voucher assistance: index transfers to local prices and monitor markets.");
  if (hi.governance) ngo.push("Expect bureaucratic hurdles and diversion risk: strengthen financial controls, partner vetting and accountability to affected people.");
  if (when) ngo.push(`Movement and access may tighten around ${when}: adjust field schedules and communications.`);
  if (!ngo.length || calm) ngo.push("A development setting: focus on long-term programmes and local partners.");

  const travel = [`Check your government's official travel advice for ${name} before you go. It changes far faster than annual data.`];
  if (conflict) travel.push("There is active armed conflict: many governments advise against all or non-essential travel to the affected regions.");
  if (crime || hi.stability) travel.push("Higher violence and crime: avoid travelling at night, use trusted transport, keep a low profile and share your itinerary.");
  if (hi.social || when) travel.push("Stay away from demonstrations" + (when ? `, especially around ${when}` : "") + ". Protests can turn violent quickly.");
  if (money) travel.push("Bring more than one way to pay: cash shortages, card problems and fast-changing prices are possible.");
  if (calm) travel.push("Generally stable: normal precautions apply.");

  const research = [];
  const top = out.drivers.slice(0, 2).map((d) => d.label);
  if (top.length) research.push(`Start with the drivers: ${top.join(" and ")} ${top.length > 1 ? "carry" : "carries"} the most risk. Explain why.`);
  else if (pillars.length) research.push(`No pillar is high risk. Ask what keeps ${name} stable and what could change that; its weakest area is ${pillars[0].label}.`);
  if (regionPos) research.push(`Put it in context: ${name} ranks ${ordinal(regionPos)} of ${peers.length} in ${row.region} and the Peers tab shows who is close.`);
  research.push("Check whether changes are real: governance moves inside the WGI confidence intervals may be noise (Data tab, Governance).");
  research.push("Test the drivers: the What-if simulator shows which indicators would move the score most.");
  research.push("Write it up: the Assessment builder turns this into a structured brief with probabilities.");

  out.caveats = [...CAVEATS];
  if (!na(s.coverage) && s.coverage < 75) out.caveats.unshift(`Only ${fixed(s.coverage, 0)}% of the indicators are available for ${name}: treat this reading with extra caution.`);
  out.actions = { business, ngo, travel, research };
  return out;
}

// The reading as a Markdown brief (for download)
export function readingMarkdown(r) {
  const out = [`# ${r.name}: what the data means in real life`, "", r.headline, "", "## On the ground", "", r.ground, ""];
  for (const d of r.drivers) out.push(`- ${d.label} (${fixed(d.score, 0)}/100). ${d.ground} Felt by: ${d.felt_by}` + (d.evidence.length ? ` Evidence: ${d.evidence.join("; ")}.` : ""));
  if (r.warnings.length) { out.push("", "## Warning signs right now", ""); for (const w of r.warnings) out.push(`- ${w.label}. ${w.meaning} Typical response: ${w.response}`); }
  if (r.near.length) out.push("", "## Close to a red line", "", ...r.near.map((n) => `- ${n}`));
  if (r.direction.length) out.push("", "## Direction", "", ...r.direction.map((d) => `- ${d}`));
  if (r.events.length) out.push("", "## Coming up", "", ...r.events.map((e) => `- ${e}`));
  for (const [key, label] of Object.entries(AUDIENCES)) if (r.actions[key]?.length) out.push("", `## What to do: ${label}`, "", ...r.actions[key].map((a) => `- ${a}`));
  out.push("", "---", "", ...r.caveats.map((c) => `*${c}*`));
  return out.join("\n") + "\n";
}
