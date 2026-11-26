// Number and text formats, the same strings as prm/interpret.py and prm/ui.py.

const buf = new DataView(new ArrayBuffer(8));

// Python's f"{x:.{d}f}": the exact binary value rounded half to even (toFixed rounds ties up, so 2.25 gives 2.3).
export function fixed(x, d = 1, { group = false, sign = false } = {}) {
  if (x === null || x === undefined) throw new TypeError("unsupported format for None");
  if (Number.isNaN(x)) return sign ? "+nan" : "nan";
  if (!Number.isFinite(x)) return (x < 0 ? "-" : sign ? "+" : "") + "inf";
  buf.setFloat64(0, x);
  const bits = buf.getBigUint64(0);
  const neg = bits >> 63n === 1n;
  const expBits = Number((bits >> 52n) & 0x7ffn);
  let m = bits & 0xfffffffffffffn;
  let e = expBits === 0 ? -1074 : expBits - 1075;
  if (expBits !== 0) m |= 1n << 52n;
  const num = m * 10n ** BigInt(d);
  let q;
  if (e >= 0) q = num << BigInt(e);
  else {
    const den = 1n << BigInt(-e);
    q = num / den;
    const twice = (num % den) * 2n;
    if (twice > den || (twice === den && q % 2n === 1n)) q += 1n;
  }
  let s = q.toString().padStart(d + 1, "0");
  let int = s.slice(0, s.length - d);
  const frac = d ? "." + s.slice(s.length - d) : "";
  if (group) int = int.replace(/\B(?=(\d{3})+$)/g, ",");
  return (neg ? "-" : sign ? "+" : "") + int + frac;
}

// Python's round(x, d) as a number (half to even on the exact value).
export const pyRound = (x, d = 0) => Number(fixed(x, d));

// A change with its sign: +1.2 / -0.4, and a plain 0.0 (0 with digits=0) when it rounds to nothing.
export function signed(v, digits = 1) {
  if (v === null || v === undefined) throw new TypeError("bad operand type for round(): 'NoneType'");
  if (Number.isNaN(v)) return "+nan";
  return pyRound(v, digits) !== 0 ? fixed(v, digits, { group: true, sign: true }) : fixed(0, digits);
}

export function fmtPopulation(p) {
  if (p === null || p === undefined || Number.isNaN(p)) return "—";
  if (p >= 1e9) return `${fixed(p / 1e9, 2)} bn`;
  if (p >= 1e6) return `${fixed(p / 1e6, 1)} m`;
  return `${fixed(p / 1e3, 0)} k`;
}

export const TREND_THRESHOLD = 1.0; // score points; smaller year-on-year moves count as steady

// Arrow + change vs last year. Up = riskier.
export function trendLabel(delta) {
  if (delta === null || delta === undefined || Number.isNaN(delta)) return "—";
  const arrow = delta >= TREND_THRESHOLD ? "▲" : delta <= -TREND_THRESHOLD ? "▼" : "■";
  return `${arrow} ${signed(delta)}`;
}

// trendLabel in words: "Riskier than in 2025: up 6.2 points"
export function trendSaid(delta, year) {
  if (delta === null || delta === undefined) throw new TypeError("'>=' not supported for NoneType");
  if (delta >= TREND_THRESHOLD) return `Riskier than in ${year - 1}: up ${fixed(delta, 1)} points`;
  if (delta <= -TREND_THRESHOLD) return `Safer than in ${year - 1}: down ${fixed(-delta, 1)} points`;
  return `Steady since ${year - 1}: moved less than ${fixed(TREND_THRESHOLD, 0)} point`;
}

export const countdown = (days) => (days === 0 ? "today" : days === 1 ? "tomorrow" : `in ${days} days`);

export const ordinal = (n) => `${n}${n % 100 >= 10 && n % 100 <= 20 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th"}`;
