import { useState, useEffect, useRef, useMemo } from "react";

// ═══════════════════════════════════════════
// DESIGN SYSTEM & SHARED COMPONENTS
// ═══════════════════════════════════════════

const FONTS_LINK = "https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap";

const LAYERS = [
  { id: 1, title: "Macro context", question: "What's happening in the world?", color: "#0F6E56", bg: "#E1F5EE", darkBg: "#04342C", darkColor: "#5DCAA5" },
  { id: 2, title: "Sector & stock selection", question: "Where should I look?", color: "#534AB7", bg: "#EEEDFE", darkBg: "#26215C", darkColor: "#AFA9EC" },
  { id: 3, title: "Deep individual analysis", question: "Is this stock worth buying?", color: "#BA7517", bg: "#FAEEDA", darkBg: "#412402", darkColor: "#FAC775" },
  { id: 4, title: "Portfolio construction & risk", question: "How do I build and protect it?", color: "#185FA5", bg: "#E6F1FB", darkBg: "#042C53", darkColor: "#85B7EB" },
];

const FRAMEWORKS = [
  { id: 1, num: "#1", name: "Goldman Sachs stock screener", firm: "Goldman Sachs", layer: 2, desc: "Screen stocks by P/E, growth, moat, dividends. Generate a professional shortlist." },
  { id: 2, num: "#2", name: "Morgan Stanley DCF valuation", firm: "Morgan Stanley", layer: 3, desc: "Full discounted cash flow with 5-year projections, WACC, sensitivity tables." },
  { id: 3, num: "#3", name: "Bridgewater risk analysis", firm: "Bridgewater", layer: 4, desc: "Correlation analysis, stress tests, tail risk, hedging strategies." },
  { id: 4, num: "#4", name: "JPMorgan earnings breakdown", firm: "JPMorgan", layer: 3, desc: "Pre-earnings analysis: beat/miss history, implied moves, trade plan." },
  { id: 5, num: "#5", name: "BlackRock portfolio construction", firm: "BlackRock", layer: 4, desc: "Asset allocation, ETF picks, rebalancing rules, investment policy." },
  { id: 6, num: "#6", name: "Citadel technical analysis", firm: "Citadel", layer: 3, desc: "Support/resistance, RSI/MACD, chart patterns, entry/exit levels." },
  { id: 7, num: "#7", name: "Harvard dividend strategy", firm: "Harvard Endowment", layer: 4, desc: "Dividend safety scores, DRIP projections, income portfolio blueprint." },
  { id: 8, num: "#8", name: "Bain competitive analysis", firm: "Bain & Company", layer: 2, desc: "Competitive landscape, moat analysis, market share, SWOT, best pick." },
  { id: 9, num: "#9", name: "Renaissance pattern finder", firm: "Renaissance Tech", layer: 3, desc: "Seasonal patterns, insider flow, short interest, statistical edges." },
  { id: 10, num: "#10", name: "McKinsey macro assessment", firm: "McKinsey", layer: 1, desc: "Interest rates, inflation, GDP, Fed policy, sector rotation signals." },
];

const getLayerColor = (layerId) => LAYERS.find(l => l.id === layerId);

// Shared UI components
function Pill({ active, onClick, children, color }) {
  return (
    <button onClick={onClick} style={{
      padding: "5px 14px", fontSize: 11, fontWeight: 500, borderRadius: 20,
      border: active ? "none" : "1px solid rgba(128,128,128,0.2)",
      background: active ? (color || "#0F6E56") : "transparent",
      color: active ? "#fff" : "rgba(128,128,128,0.6)",
      cursor: "pointer", fontFamily: "inherit", letterSpacing: "-0.01em", transition: "all 0.15s",
    }}>{children}</button>
  );
}

function OptionPills({ value, options, onChange, size = "sm" }) {
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      {options.map((opt, i) => {
        const label = typeof opt === "string" ? opt : opt.label;
        const val = typeof opt === "string" ? opt : opt.value;
        const col = typeof opt === "object" && opt.color ? opt.color : null;
        const isActive = value === val;
        return (
          <button key={i} onClick={() => onChange(val)} style={{
            padding: size === "sm" ? "4px 10px" : "6px 14px",
            fontSize: size === "sm" ? 11 : 12, fontWeight: 500, borderRadius: 20,
            border: isActive ? "none" : "1px solid rgba(128,128,128,0.2)",
            background: isActive ? (col || "rgba(15,110,86,0.15)") : "transparent",
            color: isActive ? (col ? "#fff" : "#0F6E56") : "rgba(128,128,128,0.6)",
            cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s",
          }}>{label}</button>
        );
      })}
    </div>
  );
}

function Slider({ label, value, onChange, min = 0, max = 10, step = 0.1, suffix = "%", desc }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: 16, fontWeight: 600, fontFamily: "'DM Mono', monospace", color: "#0F6E56", letterSpacing: "-0.03em" }}>
          {value > 0 && !suffix.includes("cut") && !suffix.includes("month") ? "+" : ""}{typeof value === 'number' ? (Number.isInteger(step) ? value : value.toFixed(1)) : value}{suffix}
        </span>
      </div>
      {desc && <p style={{ fontSize: 11, color: "rgba(128,128,128,0.6)", margin: "0 0 4px" }}>{desc}</p>}
      <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(parseFloat(e.target.value))} style={{ width: "100%", accentColor: "#0F6E56" }} />
    </div>
  );
}

function Card({ title, number, children, accent }) {
  return (
    <div style={{
      background: "var(--color-background-primary, #fff)", border: "1px solid rgba(128,128,128,0.12)",
      borderRadius: 16, padding: "24px 24px 20px", marginBottom: 16, position: "relative", overflow: "hidden",
    }}>
      {number && <div style={{ position: "absolute", top: 12, right: 16, fontSize: 52, fontWeight: 700, opacity: 0.04, fontFamily: "'DM Mono', monospace" }}>{String(number).padStart(2, "0")}</div>}
      {title && <h3 style={{
        fontSize: 14, fontWeight: 600, marginBottom: 16, letterSpacing: "-0.02em", textTransform: "uppercase",
        display: "flex", alignItems: "center", gap: 8,
      }}>
        {number && <span style={{
          width: 20, height: 20, borderRadius: 5, background: accent || "#0F6E56", color: "#fff",
          fontSize: 10, fontWeight: 600, display: "inline-flex", alignItems: "center", justifyContent: "center",
        }}>{number}</span>}
        {title}
      </h3>}
      {children}
    </div>
  );
}

function InfoBox({ children, color = "#0F6E56", bg = "#E1F5EE" }) {
  return <div style={{ padding: 14, borderRadius: 10, background: bg, fontSize: 12, color, lineHeight: 1.6 }}>{children}</div>;
}

function MetricRow({ label, value, color }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid rgba(128,128,128,0.08)" }}>
      <span style={{ fontSize: 12, color: "rgba(128,128,128,0.6)" }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 600, fontFamily: "'DM Mono', monospace", color: color || "inherit" }}>{value}</span>
    </div>
  );
}

function BackButton({ onClick }) {
  return (
    <button onClick={onClick} style={{
      display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 14px", fontSize: 12,
      fontWeight: 500, borderRadius: 20, border: "1px solid rgba(128,128,128,0.2)",
      background: "transparent", color: "rgba(128,128,128,0.6)", cursor: "pointer",
      fontFamily: "inherit", marginBottom: 20, transition: "all 0.15s",
    }}>
      <span style={{ fontSize: 14 }}>←</span> Back to hub
    </button>
  );
}

function FrameworkHeader({ num, name, firm, desc }) {
  return (
    <div style={{ marginBottom: 28, paddingBottom: 20, borderBottom: "1px solid rgba(128,128,128,0.12)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <div style={{ width: 7, height: 7, borderRadius: 2, background: "#0F6E56" }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: "#0F6E56", textTransform: "uppercase", letterSpacing: "0.08em" }}>{firm}</span>
      </div>
      <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.03em", margin: "0 0 6px" }}>{name}</h1>
      <p style={{ fontSize: 13, color: "rgba(128,128,128,0.6)", margin: 0, maxWidth: 500, lineHeight: 1.5 }}>{desc}</p>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #10 — MCKINSEY MACRO ASSESSMENT
// ═══════════════════════════════════════════

const CYCLE_PHASES = [
  { id: "early", label: "Early expansion", sectors: ["Tech", "Cons. disc.", "Industrials"], desc: "Rates bottoming, credit expanding, earnings inflecting upward." },
  { id: "mid", label: "Mid expansion", sectors: ["Tech", "Industrials", "Materials"], desc: "Broad growth, rising confidence. Quality growth outperforms." },
  { id: "late", label: "Late expansion", sectors: ["Energy", "Materials", "Healthcare"], desc: "Rates peaking, margins compressing. Defensives outperform." },
  { id: "recession", label: "Recession", sectors: ["Healthcare", "Utilities", "Staples"], desc: "Earnings declining. Capital preservation priority." },
];

const SECTORS_ALL = ["Technology","Healthcare","Financials","Energy","Cons. discretionary","Cons. staples","Industrials","Materials","Utilities","Real estate","Comm. services"];
const IMPACT_OPTS = ["Strong tailwind","Mild tailwind","Neutral","Mild headwind","Strong headwind"];
const GLOBAL_RISKS = ["Geopolitical conflict","Trade war / tariffs","Supply chain disruption","Sovereign debt crisis","Energy price shock","China slowdown","Cyber attack","Pandemic risk"];

function McKinseyMacro({ onBack }) {
  const [s, set] = useState({
    cycle: "late", fedRate: 4.5, tenY: 4.2, cpi: 3.2, coreCpi: 3.0, gdp: 2.1, epsGrowth: 8,
    dxy: "stable", unemp: 4.1, sentiment: "neutral", fedOutlook: "hold", cuts: 2,
    sectors: Object.fromEntries(SECTORS_ALL.map(s => [s, "Neutral"])),
    risks: Object.fromEntries(GLOBAL_RISKS.map(r => [r, 2])),
  });
  const u = (k, v) => set(p => ({ ...p, [k]: v }));
  const un = (k, sk, v) => set(p => ({ ...p, [k]: { ...p[k], [sk]: v } }));
  const spread = (s.tenY - s.fedRate).toFixed(2);
  const realRate = (s.fedRate - s.cpi).toFixed(1);
  const phase = CYCLE_PHASES.find(p => p.id === s.cycle);
  const rateStance = s.fedRate > 4.5 ? "restrictive" : s.fedRate > 3 ? "moderately tight" : s.fedRate > 1.5 ? "neutral" : "accommodative";
  const headwinds = SECTORS_ALL.filter(x => s.sectors[x]?.includes("headwind"));
  const tailwinds = SECTORS_ALL.filter(x => s.sectors[x]?.includes("tailwind"));
  const highRisks = GLOBAL_RISKS.filter(r => s.risks[r] >= 4);

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#10" name="Macro impact assessment" firm="McKinsey Global Institute" desc="Configure macro conditions to generate a portfolio strategy briefing." />

      <Card title="Economic cycle position" number={1}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, marginBottom: 14 }}>
          {CYCLE_PHASES.map(p => (
            <button key={p.id} onClick={() => u("cycle", p.id)} style={{
              padding: "12px 8px", borderRadius: 10, textAlign: "left", fontFamily: "inherit", cursor: "pointer", transition: "all 0.15s",
              border: s.cycle === p.id ? "2px solid #0F6E56" : "1px solid rgba(128,128,128,0.15)",
              background: s.cycle === p.id ? "#E1F5EE" : "transparent",
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: s.cycle === p.id ? "#0F6E56" : "rgba(128,128,128,0.5)", marginBottom: 3 }}>{p.label}</div>
              <div style={{ fontSize: 9, color: s.cycle === p.id ? "#0F6E56" : "rgba(128,128,128,0.4)" }}>{p.sectors.join(", ")}</div>
            </button>
          ))}
        </div>
        <InfoBox>{phase.desc}</InfoBox>
      </Card>

      <Card title="Interest rate environment" number={2}>
        <Slider label="Fed funds rate" value={s.fedRate} onChange={v => u("fedRate", v)} min={0} max={8} step={0.25} />
        <Slider label="10-year yield" value={s.tenY} onChange={v => u("tenY", v)} min={0} max={7} step={0.1} />
        <MetricRow label="Yield curve spread" value={`${spread > 0 ? "+" : ""}${spread}%`} color={spread < 0 ? "#A32D2D" : "#0F6E56"} />
        <MetricRow label="Stance" value={rateStance} />
      </Card>

      <Card title="Inflation analysis" number={3}>
        <Slider label="Headline CPI (YoY)" value={s.cpi} onChange={v => u("cpi", v)} min={-1} max={10} step={0.1} />
        <Slider label="Core CPI (YoY)" value={s.coreCpi} onChange={v => u("coreCpi", v)} min={-1} max={8} step={0.1} />
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <div style={{ flex: 1, padding: 10, borderRadius: 8, background: s.cpi <= 2.5 ? "#E1F5EE" : s.cpi <= 4 ? "#FAEEDA" : "#FCEBEB", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>Status</div>
            <div style={{ fontSize: 12, fontWeight: 600, color: s.cpi <= 2.5 ? "#0F6E56" : s.cpi <= 4 ? "#BA7517" : "#A32D2D" }}>
              {s.cpi <= 2.5 ? "At target" : s.cpi <= 4 ? "Above target" : "Elevated"}
            </div>
          </div>
          <div style={{ flex: 1, padding: 10, borderRadius: 8, background: "#E1F5EE", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>Real rate</div>
            <div style={{ fontSize: 12, fontWeight: 600, fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>{realRate}%</div>
          </div>
        </div>
      </Card>

      <Card title="GDP & corporate earnings" number={4}>
        <Slider label="GDP growth" value={s.gdp} onChange={v => u("gdp", v)} min={-4} max={6} step={0.1} />
        <Slider label="S&P 500 EPS growth est." value={s.epsGrowth} onChange={v => u("epsGrowth", v)} min={-20} max={30} step={1} />
      </Card>

      <Card title="USD strength" number={5}>
        <OptionPills value={s.dxy} options={["strengthening", "stable", "weakening"]} onChange={v => u("dxy", v)} size="md" />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 12 }}>
          <div style={{ padding: 10, borderRadius: 8, border: "1px solid rgba(128,128,128,0.12)", fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>Domestic</div>
            <div style={{ color: s.dxy === "strengthening" ? "#0F6E56" : s.dxy === "weakening" ? "#A32D2D" : "rgba(128,128,128,0.5)" }}>
              {s.dxy === "strengthening" ? "↑ Advantage" : s.dxy === "weakening" ? "↓ Drag" : "→ Neutral"}
            </div>
          </div>
          <div style={{ padding: 10, borderRadius: 8, border: "1px solid rgba(128,128,128,0.12)", fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>International</div>
            <div style={{ color: s.dxy === "weakening" ? "#0F6E56" : s.dxy === "strengthening" ? "#A32D2D" : "rgba(128,128,128,0.5)" }}>
              {s.dxy === "weakening" ? "↑ FX tailwind" : s.dxy === "strengthening" ? "↓ FX headwind" : "→ Neutral"}
            </div>
          </div>
        </div>
      </Card>

      <Card title="Employment & consumer" number={6}>
        <Slider label="Unemployment rate" value={s.unemp} onChange={v => u("unemp", v)} min={2} max={12} step={0.1} />
        <div style={{ marginTop: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 500, display: "block", marginBottom: 6 }}>Consumer sentiment</span>
          <OptionPills value={s.sentiment} options={["strong", "neutral", "weakening", "recessionary"]} onChange={v => u("sentiment", v)} />
        </div>
      </Card>

      <Card title="Fed policy outlook" number={7}>
        <div style={{ marginBottom: 14 }}>
          <span style={{ fontSize: 12, fontWeight: 500, display: "block", marginBottom: 6 }}>Next 6-12 month stance</span>
          <OptionPills value={s.fedOutlook} options={["hawkish", "hold", "dovish"]} onChange={v => u("fedOutlook", v)} size="md" />
        </div>
        <Slider label="Expected rate cuts (12mo)" value={s.cuts} onChange={v => u("cuts", v)} min={0} max={8} step={1} suffix=" cuts" />
      </Card>

      <Card title="Global risk factors" number={8}>
        {GLOBAL_RISKS.map(r => (
          <div key={r} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 0", borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
            <span style={{ fontSize: 11, flex: 1 }}>{r}</span>
            <OptionPills value={s.risks[r]} options={[{value:1,label:"1",color:"#0F6E56"},{value:2,label:"2",color:"#1D9E75"},{value:3,label:"3",color:"#BA7517"},{value:4,label:"4",color:"#D85A30"},{value:5,label:"5",color:"#A32D2D"}]} onChange={v => un("risks", r, v)} />
          </div>
        ))}
      </Card>

      <Card title="Sector rotation heat map" number={9}>
        {SECTORS_ALL.map(sec => (
          <div key={sec} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
            <span style={{ fontSize: 11, width: 130, flexShrink: 0, color: "rgba(128,128,128,0.6)" }}>{sec}</span>
            <div style={{ display: "flex", gap: 3, flex: 1 }}>
              {IMPACT_OPTS.map(opt => {
                const cm = {"Strong tailwind":"#0F6E56","Mild tailwind":"#5DCAA5","Neutral":"rgba(128,128,128,0.4)","Mild headwind":"#D85A30","Strong headwind":"#A32D2D"};
                return <button key={opt} onClick={() => un("sectors", sec, opt)} title={opt} style={{
                  flex: 1, height: 24, borderRadius: 5, cursor: "pointer", transition: "all 0.15s",
                  border: s.sectors[sec] === opt ? `2px solid ${cm[opt]}` : "1px solid rgba(128,128,128,0.12)",
                  background: s.sectors[sec] === opt ? cm[opt] : "transparent",
                }} />;
              })}
            </div>
          </div>
        ))}
      </Card>

      <Card title="Executive action plan" number={10} accent="#0F6E56">
        <div style={{ padding: 14, borderRadius: 10, background: "#0F6E56", color: "#fff", marginBottom: 14 }}>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", opacity: 0.7, marginBottom: 4 }}>Regime</div>
          <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.02em" }}>{phase.label} cycle · {rateStance} policy</div>
        </div>
        {[
          { t: "Rates", c: `Fed at ${s.fedRate.toFixed(1)}% (${rateStance}). ${s.fedRate > 4 ? "Favors value and dividends." : "Supports growth stocks."}` },
          { t: "Inflation", c: `CPI ${s.cpi.toFixed(1)}%. ${s.cpi > 3 ? "Add inflation hedges." : "Standard allocation sufficient."}` },
          { t: "Growth", c: `GDP ${s.gdp.toFixed(1)}%. ${s.gdp < 1 ? "Increase defensives." : "Maintain equity overweight."}` },
          { t: "Sectors", c: `${tailwinds.length > 0 ? `Tailwinds: ${tailwinds.slice(0,3).join(", ")}. ` : ""}${headwinds.length > 0 ? `Headwinds: ${headwinds.slice(0,3).join(", ")}.` : ""}` },
          { t: "Risks", c: highRisks.length > 0 ? `Elevated: ${highRisks.join(", ")}. Consider hedges.` : "No severe risks flagged." },
        ].map((item, i) => (
          <div key={i} style={{ padding: "8px 0", borderBottom: "1px solid rgba(128,128,128,0.08)", display: "flex", gap: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: "#0F6E56", minWidth: 65, textTransform: "uppercase", letterSpacing: "0.03em" }}>{item.t}</span>
            <span style={{ fontSize: 12, color: "rgba(128,128,128,0.6)", lineHeight: 1.5 }}>{item.c}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #1 — GOLDMAN SACHS STOCK SCREENER
// ═══════════════════════════════════════════

function GoldmanScreener({ onBack }) {
  const [criteria, setCriteria] = useState({
    minMktCap: "large", sector: "all", peRange: "below_avg", minDivYield: 0, minRevGrowth: 5, maxDebtEquity: 1.5, moat: "any",
  });
  const [stocks, setStocks] = useState([
    { ticker: "AAPL", name: "Apple Inc", sector: "Technology", pe: 28.5, sectorPe: 32.1, revGrowth5y: 8.2, deRatio: 1.73, divYield: 0.55, payoutRatio: 15.7, moat: "Strong", riskRating: 3, bull: 245, bear: 175, entry: "185-195", stopLoss: 172 },
    { ticker: "MSFT", name: "Microsoft", sector: "Technology", pe: 34.2, sectorPe: 32.1, revGrowth5y: 14.1, deRatio: 0.35, divYield: 0.74, payoutRatio: 25.3, moat: "Strong", riskRating: 2, bull: 480, bear: 360, entry: "390-410", stopLoss: 370 },
    { ticker: "JNJ", name: "Johnson & Johnson", sector: "Healthcare", pe: 15.8, sectorPe: 22.4, revGrowth5y: 3.9, deRatio: 0.44, divYield: 2.95, payoutRatio: 46.6, moat: "Strong", riskRating: 3, bull: 185, bear: 145, entry: "150-160", stopLoss: 140 },
    { ticker: "JPM", name: "JPMorgan Chase", sector: "Financials", pe: 12.1, sectorPe: 14.8, revGrowth5y: 7.8, deRatio: 1.52, divYield: 2.22, payoutRatio: 27.0, moat: "Strong", riskRating: 4, bull: 235, bear: 170, entry: "185-200", stopLoss: 168 },
    { ticker: "PG", name: "Procter & Gamble", sector: "Cons. staples", pe: 24.3, sectorPe: 22.1, revGrowth5y: 4.5, deRatio: 0.74, divYield: 2.41, payoutRatio: 58.6, moat: "Strong", riskRating: 2, bull: 180, bear: 145, entry: "152-160", stopLoss: 142 },
    { ticker: "V", name: "Visa Inc", sector: "Financials", pe: 30.5, sectorPe: 14.8, revGrowth5y: 11.2, deRatio: 0.53, divYield: 0.76, payoutRatio: 23.2, moat: "Strong", riskRating: 3, bull: 320, bear: 250, entry: "265-280", stopLoss: 245 },
    { ticker: "UNH", name: "UnitedHealth", sector: "Healthcare", pe: 19.5, sectorPe: 22.4, revGrowth5y: 12.8, deRatio: 0.72, divYield: 1.48, payoutRatio: 28.8, moat: "Moderate", riskRating: 4, bull: 610, bear: 460, entry: "490-520", stopLoss: 450 },
    { ticker: "HD", name: "Home Depot", sector: "Cons. disc.", pe: 22.8, sectorPe: 25.3, revGrowth5y: 7.1, deRatio: 9.14, divYield: 2.52, payoutRatio: 57.4, moat: "Strong", riskRating: 4, bull: 410, bear: 310, entry: "330-350", stopLoss: 300 },
    { ticker: "XOM", name: "Exxon Mobil", sector: "Energy", pe: 13.2, sectorPe: 11.8, revGrowth5y: 9.6, deRatio: 0.21, divYield: 3.35, payoutRatio: 44.2, moat: "Moderate", riskRating: 5, bull: 130, bear: 90, entry: "100-110", stopLoss: 88 },
    { ticker: "COST", name: "Costco", sector: "Cons. staples", pe: 50.2, sectorPe: 22.1, revGrowth5y: 12.4, deRatio: 0.31, divYield: 0.58, payoutRatio: 29.1, moat: "Strong", riskRating: 2, bull: 950, bear: 720, entry: "760-800", stopLoss: 700 },
  ]);
  const [sort, setSort] = useState("riskRating");

  const sorted = [...stocks].sort((a, b) => sort === "divYield" || sort === "revGrowth5y" ? b[sort] - a[sort] : a[sort] - b[sort]);
  const moatColor = m => m === "Strong" ? "#0F6E56" : m === "Moderate" ? "#BA7517" : "#A32D2D";
  const riskColor = r => r <= 2 ? "#0F6E56" : r <= 4 ? "#BA7517" : "#A32D2D";

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#1" name="Stock screener" firm="Goldman Sachs" desc="Screen equities across fundamentals, moat, risk, and price targets." />

      <Card title="Screening criteria" number={1}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <span style={{ fontSize: 11, fontWeight: 500, display: "block", marginBottom: 4 }}>Market cap</span>
            <OptionPills value={criteria.minMktCap} options={["large", "mid", "small", "any"]} onChange={v => setCriteria(p => ({...p, minMktCap: v}))} />
          </div>
          <div>
            <span style={{ fontSize: 11, fontWeight: 500, display: "block", marginBottom: 4 }}>Moat strength</span>
            <OptionPills value={criteria.moat} options={["Strong", "Moderate", "any"]} onChange={v => setCriteria(p => ({...p, moat: v}))} />
          </div>
        </div>
        <div style={{ marginTop: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 500, display: "block", marginBottom: 4 }}>Sort by</span>
          <OptionPills value={sort} options={[{value:"riskRating",label:"Risk (low→high)"},{value:"pe",label:"P/E (low→high)"},{value:"divYield",label:"Dividend yield"},{value:"revGrowth5y",label:"Revenue growth"}]} onChange={setSort} />
        </div>
      </Card>

      <Card title="Screening results" number={2}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid rgba(128,128,128,0.15)" }}>
                {["Ticker","P/E","vs Sect.","Rev 5Y","D/E","Div %","Moat","Risk","Bull","Bear","Entry"].map(h => (
                  <th key={h} style={{ padding: "6px 6px", textAlign: "left", fontWeight: 600, fontSize: 10, color: "rgba(128,128,128,0.5)", textTransform: "uppercase", letterSpacing: "0.03em" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map(s => (
                <tr key={s.ticker} style={{ borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
                  <td style={{ padding: "8px 6px" }}><span style={{ fontWeight: 600, fontFamily: "'DM Mono', monospace" }}>{s.ticker}</span><br/><span style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>{s.name}</span></td>
                  <td style={{ padding: "8px 6px", fontFamily: "'DM Mono', monospace" }}>{s.pe}</td>
                  <td style={{ padding: "8px 6px", color: s.pe < s.sectorPe ? "#0F6E56" : "#A32D2D", fontFamily: "'DM Mono', monospace" }}>{s.pe < s.sectorPe ? "↓" : "↑"}{Math.abs(s.pe - s.sectorPe).toFixed(1)}</td>
                  <td style={{ padding: "8px 6px", fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>{s.revGrowth5y}%</td>
                  <td style={{ padding: "8px 6px", fontFamily: "'DM Mono', monospace", color: s.deRatio > 2 ? "#A32D2D" : "inherit" }}>{s.deRatio}</td>
                  <td style={{ padding: "8px 6px", fontFamily: "'DM Mono', monospace" }}>{s.divYield}%</td>
                  <td style={{ padding: "8px 6px" }}><span style={{ padding: "2px 6px", borderRadius: 8, fontSize: 9, fontWeight: 600, background: moatColor(s.moat) + "18", color: moatColor(s.moat) }}>{s.moat}</span></td>
                  <td style={{ padding: "8px 6px" }}><span style={{ fontWeight: 600, color: riskColor(s.riskRating) }}>{s.riskRating}/10</span></td>
                  <td style={{ padding: "8px 6px", fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>${s.bull}</td>
                  <td style={{ padding: "8px 6px", fontFamily: "'DM Mono', monospace", color: "#A32D2D" }}>${s.bear}</td>
                  <td style={{ padding: "8px 6px", fontSize: 10 }}>{s.entry}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #2 — MORGAN STANLEY DCF VALUATION
// ═══════════════════════════════════════════

function MorganStanleyDCF({ onBack }) {
  const [d, setD] = useState({
    revenue: 400, revGrowth: [12, 10, 8, 7, 5], opMargin: 30, taxRate: 21, capexPct: 5, depPct: 4,
    wacc: 10, termGrowth: 3, exitMultiple: 15, sharesOut: 15.2, currentPrice: 195,
  });
  const u = (k, v) => setD(p => ({ ...p, [k]: v }));

  const projections = useMemo(() => {
    let rev = d.revenue;
    const years = [];
    for (let i = 0; i < 5; i++) {
      rev = rev * (1 + d.revGrowth[i] / 100);
      const ebit = rev * (d.opMargin / 100);
      const nopat = ebit * (1 - d.taxRate / 100);
      const capex = rev * (d.capexPct / 100);
      const dep = rev * (d.depPct / 100);
      const fcf = nopat + dep - capex;
      const pvFactor = Math.pow(1 + d.wacc / 100, i + 1);
      years.push({ year: i + 1, rev: Math.round(rev * 10) / 10, ebit: Math.round(ebit * 10) / 10, fcf: Math.round(fcf * 10) / 10, pvFcf: Math.round(fcf / pvFactor * 10) / 10 });
    }
    const lastFcf = years[4].fcf;
    const tvPerp = (lastFcf * (1 + d.termGrowth / 100)) / ((d.wacc - d.termGrowth) / 100);
    const tvExit = years[4].ebit * d.exitMultiple;
    const pvFactor5 = Math.pow(1 + d.wacc / 100, 5);
    const pvTvPerp = tvPerp / pvFactor5;
    const pvTvExit = tvExit / pvFactor5;
    const sumPvFcf = years.reduce((a, y) => a + y.pvFcf, 0);
    const evPerp = sumPvFcf + pvTvPerp;
    const evExit = sumPvFcf + pvTvExit;
    const fairPerp = Math.round(evPerp / d.sharesOut * 10) / 10;
    const fairExit = Math.round(evExit / d.sharesOut * 10) / 10;
    const fairAvg = Math.round((fairPerp + fairExit) / 2 * 10) / 10;
    const upside = Math.round((fairAvg / d.currentPrice - 1) * 1000) / 10;
    return { years, tvPerp: Math.round(tvPerp), tvExit: Math.round(tvExit), pvTvPerp: Math.round(pvTvPerp), pvTvExit: Math.round(pvTvExit), sumPvFcf: Math.round(sumPvFcf * 10) / 10, evPerp: Math.round(evPerp), evExit: Math.round(evExit), fairPerp, fairExit, fairAvg, upside };
  }, [d]);

  const verdict = projections.upside > 15 ? "Undervalued" : projections.upside < -10 ? "Overvalued" : "Fairly valued";
  const verdictColor = projections.upside > 15 ? "#0F6E56" : projections.upside < -10 ? "#A32D2D" : "#BA7517";

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#2" name="DCF valuation deep dive" firm="Morgan Stanley" desc="Build a full discounted cash flow model with sensitivity analysis." />

      <Card title="Input assumptions" number={1}>
        <Slider label="Base revenue ($B)" value={d.revenue} onChange={v => u("revenue", v)} min={10} max={1000} step={10} suffix="B" />
        <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 8 }}>Revenue growth by year (%)</div>
        <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
          {d.revGrowth.map((g, i) => (
            <div key={i} style={{ flex: 1, textAlign: "center" }}>
              <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>Yr {i + 1}</div>
              <input type="number" value={g} onChange={e => { const ng = [...d.revGrowth]; ng[i] = parseFloat(e.target.value) || 0; u("revGrowth", ng); }}
                style={{ width: "100%", textAlign: "center", padding: "4px", fontSize: 12, fontFamily: "'DM Mono', monospace", border: "1px solid rgba(128,128,128,0.2)", borderRadius: 6, background: "transparent", color: "inherit" }} />
            </div>
          ))}
        </div>
        <Slider label="Operating margin" value={d.opMargin} onChange={v => u("opMargin", v)} min={5} max={60} step={1} />
        <Slider label="WACC" value={d.wacc} onChange={v => u("wacc", v)} min={5} max={20} step={0.5} />
        <Slider label="Terminal growth" value={d.termGrowth} onChange={v => u("termGrowth", v)} min={1} max={5} step={0.5} />
        <Slider label="Exit multiple (EV/EBIT)" value={d.exitMultiple} onChange={v => u("exitMultiple", v)} min={5} max={30} step={1} suffix="x" />
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, marginBottom: 4 }}>Shares out (B)</div>
            <input type="number" value={d.sharesOut} step={0.1} onChange={e => u("sharesOut", parseFloat(e.target.value) || 1)}
              style={{ width: "100%", padding: "6px 8px", fontSize: 12, fontFamily: "'DM Mono', monospace", border: "1px solid rgba(128,128,128,0.2)", borderRadius: 6, background: "transparent", color: "inherit" }} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, marginBottom: 4 }}>Current price ($)</div>
            <input type="number" value={d.currentPrice} step={1} onChange={e => u("currentPrice", parseFloat(e.target.value) || 1)}
              style={{ width: "100%", padding: "6px 8px", fontSize: 12, fontFamily: "'DM Mono', monospace", border: "1px solid rgba(128,128,128,0.2)", borderRadius: 6, background: "transparent", color: "inherit" }} />
          </div>
        </div>
      </Card>

      <Card title="5-year projections ($B)" number={2}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid rgba(128,128,128,0.15)" }}>
              {["Year","Revenue","EBIT","FCF","PV of FCF"].map(h => <th key={h} style={{ padding: "6px", textAlign: "right", fontWeight: 600, fontSize: 10, color: "rgba(128,128,128,0.5)", textTransform: "uppercase" }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {projections.years.map(y => (
              <tr key={y.year} style={{ borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
                <td style={{ padding: "6px", fontWeight: 600 }}>Year {y.year}</td>
                <td style={{ padding: "6px", textAlign: "right", fontFamily: "'DM Mono', monospace" }}>{y.rev}</td>
                <td style={{ padding: "6px", textAlign: "right", fontFamily: "'DM Mono', monospace" }}>{y.ebit}</td>
                <td style={{ padding: "6px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>{y.fcf}</td>
                <td style={{ padding: "6px", textAlign: "right", fontFamily: "'DM Mono', monospace" }}>{y.pvFcf}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Valuation summary" number={3}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 14 }}>
          <div style={{ padding: 12, borderRadius: 10, background: "#E1F5EE", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>Perpetuity method</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>${projections.fairPerp}</div>
          </div>
          <div style={{ padding: 12, borderRadius: 10, background: "#E6F1FB", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>Exit multiple method</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#185FA5" }}>${projections.fairExit}</div>
          </div>
        </div>
        <div style={{ padding: 16, borderRadius: 12, background: verdictColor, color: "#fff", textAlign: "center" }}>
          <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.06em", opacity: 0.7, marginBottom: 4 }}>Blended fair value</div>
          <div style={{ fontSize: 28, fontWeight: 700, fontFamily: "'DM Mono', monospace" }}>${projections.fairAvg}</div>
          <div style={{ fontSize: 13, marginTop: 4 }}>{verdict} · {projections.upside > 0 ? "+" : ""}{projections.upside}% vs current ${d.currentPrice}</div>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #3 — BRIDGEWATER RISK ANALYSIS
// ═══════════════════════════════════════════

function BridgewaterRisk({ onBack }) {
  const [holdings, setHoldings] = useState([
    { name: "US Large Cap", pct: 35, sector: "Equities", liquidity: "High", rateSens: "Medium", drawdown: -34 },
    { name: "US Mid Cap", pct: 10, sector: "Equities", liquidity: "High", rateSens: "Medium", drawdown: -41 },
    { name: "International Dev.", pct: 12, sector: "Equities", liquidity: "High", rateSens: "Low", drawdown: -38 },
    { name: "Emerging Markets", pct: 8, sector: "Equities", liquidity: "Medium", rateSens: "High", drawdown: -52 },
    { name: "US Aggregate Bonds", pct: 15, sector: "Fixed income", liquidity: "High", rateSens: "High", drawdown: -13 },
    { name: "High Yield Bonds", pct: 5, sector: "Fixed income", liquidity: "Medium", rateSens: "Medium", drawdown: -26 },
    { name: "REITs", pct: 7, sector: "Alternatives", liquidity: "Medium", rateSens: "High", drawdown: -39 },
    { name: "Commodities", pct: 5, sector: "Alternatives", liquidity: "Medium", rateSens: "Low", drawdown: -30 },
    { name: "Cash", pct: 3, sector: "Cash", liquidity: "High", rateSens: "None", drawdown: 0 },
  ]);

  const sectorBreakdown = {};
  holdings.forEach(h => { sectorBreakdown[h.sector] = (sectorBreakdown[h.sector] || 0) + h.pct; });
  const equityPct = sectorBreakdown["Equities"] || 0;
  const estDrawdown = Math.round(holdings.reduce((a, h) => a + (h.pct / 100) * h.drawdown, 0));
  const concRisk = equityPct > 70 ? "High" : equityPct > 50 ? "Moderate" : "Low";

  const updateHolding = (i, field, val) => {
    const nh = [...holdings];
    nh[i] = { ...nh[i], [field]: val };
    setHoldings(nh);
  };

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#3" name="Risk analysis framework" firm="Bridgewater Associates" desc="Evaluate portfolio risk: correlations, stress tests, tail scenarios, hedging." />

      <Card title="Portfolio holdings" number={1}>
        <div style={{ fontSize: 11, color: "rgba(128,128,128,0.5)", marginBottom: 10 }}>Adjust allocation percentages. Total should equal 100%.</div>
        {holdings.map((h, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
            <span style={{ fontSize: 12, flex: 1, minWidth: 0 }}>{h.name}</span>
            <span style={{ fontSize: 10, color: "rgba(128,128,128,0.4)", width: 70 }}>{h.sector}</span>
            <input type="number" value={h.pct} min={0} max={100} onChange={e => updateHolding(i, "pct", parseFloat(e.target.value) || 0)}
              style={{ width: 50, textAlign: "center", padding: "3px", fontSize: 11, fontFamily: "'DM Mono', monospace", border: "1px solid rgba(128,128,128,0.2)", borderRadius: 5, background: "transparent", color: "inherit" }} />
            <span style={{ fontSize: 10, color: "rgba(128,128,128,0.4)" }}>%</span>
          </div>
        ))}
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8, fontSize: 12, fontWeight: 600 }}>
          Total: <span style={{ fontFamily: "'DM Mono', monospace", marginLeft: 8, color: Math.abs(holdings.reduce((a, h) => a + h.pct, 0) - 100) > 0.1 ? "#A32D2D" : "#0F6E56" }}>{holdings.reduce((a, h) => a + h.pct, 0)}%</span>
        </div>
      </Card>

      <Card title="Concentration risk" number={2}>
        {Object.entries(sectorBreakdown).map(([sec, pct]) => (
          <div key={sec} style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
              <span>{sec}</span>
              <span style={{ fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>{pct}%</span>
            </div>
            <div style={{ height: 6, borderRadius: 3, background: "rgba(128,128,128,0.1)", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${pct}%`, borderRadius: 3, background: pct > 50 ? "#A32D2D" : pct > 30 ? "#BA7517" : "#0F6E56", transition: "width 0.3s" }} />
            </div>
          </div>
        ))}
        <div style={{ marginTop: 12, padding: 10, borderRadius: 8, border: "1px solid rgba(128,128,128,0.12)", fontSize: 12 }}>
          Concentration risk: <span style={{ fontWeight: 600, color: concRisk === "High" ? "#A32D2D" : concRisk === "Moderate" ? "#BA7517" : "#0F6E56" }}>{concRisk}</span> — Equity allocation at {equityPct}%
        </div>
      </Card>

      <Card title="Recession stress test" number={3}>
        <div style={{ fontSize: 12, color: "rgba(128,128,128,0.6)", marginBottom: 10 }}>Estimated portfolio drawdown based on historical worst-case per asset class.</div>
        {holdings.filter(h => h.pct > 0).map((h, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
            <span style={{ fontSize: 11, flex: 1 }}>{h.name}</span>
            <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: "#A32D2D", width: 40, textAlign: "right" }}>{h.drawdown}%</span>
            <span style={{ fontSize: 10, color: "rgba(128,128,128,0.4)" }}>×</span>
            <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", width: 30, textAlign: "right" }}>{h.pct}%</span>
            <span style={{ fontSize: 10, color: "rgba(128,128,128,0.4)" }}>=</span>
            <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: "#A32D2D", width: 45, textAlign: "right" }}>{Math.round(h.pct / 100 * h.drawdown * 10) / 10}%</span>
          </div>
        ))}
        <div style={{ marginTop: 12, padding: 14, borderRadius: 10, background: Math.abs(estDrawdown) > 25 ? "#FCEBEB" : Math.abs(estDrawdown) > 15 ? "#FAEEDA" : "#E1F5EE", textAlign: "center" }}>
          <div style={{ fontSize: 9, textTransform: "uppercase", color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>Estimated portfolio drawdown</div>
          <div style={{ fontSize: 24, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: Math.abs(estDrawdown) > 25 ? "#A32D2D" : Math.abs(estDrawdown) > 15 ? "#BA7517" : "#0F6E56" }}>{estDrawdown}%</div>
        </div>
      </Card>

      <Card title="Hedging recommendations" number={4}>
        {[
          { cond: equityPct > 60, rec: "Reduce equity concentration below 60% or add put protection on broad index.", priority: "High" },
          { cond: (sectorBreakdown["Fixed income"] || 0) < 15, rec: "Increase fixed income allocation to at least 15-20% for downside buffer.", priority: "Medium" },
          { cond: (sectorBreakdown["Alternatives"] || 0) < 10, rec: "Add alternative assets (gold, managed futures) for decorrelation.", priority: "Medium" },
          { cond: holdings.some(h => h.pct > 30), rec: "No single asset class should exceed 30% — rebalance largest position.", priority: "High" },
          { cond: Math.abs(estDrawdown) > 25, rec: "Consider tail-risk hedging: VIX calls or put spreads on SPY.", priority: "High" },
        ].filter(r => r.cond).map((r, i) => (
          <div key={i} style={{ display: "flex", gap: 8, padding: "10px 0", borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
            <span style={{ fontSize: 9, fontWeight: 600, padding: "2px 8px", borderRadius: 8, height: "fit-content",
              background: r.priority === "High" ? "#FCEBEB" : "#FAEEDA",
              color: r.priority === "High" ? "#A32D2D" : "#BA7517",
            }}>{r.priority}</span>
            <span style={{ fontSize: 12, color: "rgba(128,128,128,0.6)", lineHeight: 1.5 }}>{r.rec}</span>
          </div>
        ))}
        {![equityPct > 60, (sectorBreakdown["Fixed income"] || 0) < 15, Math.abs(estDrawdown) > 25].some(Boolean) && (
          <InfoBox>Portfolio risk profile is well-balanced. Maintain current hedging levels.</InfoBox>
        )}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #4 — JPMORGAN EARNINGS BREAKDOWN
// ═══════════════════════════════════════════

function JPMorganEarnings({ onBack }) {
  const [ticker, setTicker] = useState("AAPL");
  const [data, setData] = useState({
    quarters: [
      { q: "Q1 2025", epsEst: 1.58, epsActual: 1.65, revEst: 117.2, revActual: 119.1, reaction: +2.8 },
      { q: "Q4 2024", epsEst: 2.35, epsActual: 2.40, revEst: 124.1, revActual: 124.3, reaction: -1.2 },
      { q: "Q3 2024", epsEst: 1.46, epsActual: 1.64, revEst: 89.3, revActual: 94.9, reaction: +6.1 },
      { q: "Q2 2024", epsEst: 1.34, epsActual: 1.40, revEst: 84.4, revActual: 85.8, reaction: -0.3 },
    ],
    upcoming: { q: "Q2 2025", epsEst: 1.71, revEst: 128.5, impliedMove: 4.2, date: "Jul 24" },
    segments: [
      { name: "iPhone", pct: 52, trend: "stable" },
      { name: "Services", pct: 26, trend: "growing" },
      { name: "Mac", pct: 10, trend: "recovering" },
      { name: "iPad", pct: 7, trend: "stable" },
      { name: "Wearables", pct: 5, trend: "declining" },
    ],
    keyMetrics: ["Services revenue growth rate", "iPhone ASP trends", "China market performance", "Gross margin expansion", "Capital return program updates"],
  });

  const beatCount = data.quarters.filter(q => q.epsActual > q.epsEst).length;

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#4" name="Earnings breakdown" firm="JPMorgan Chase" desc="Pre-earnings analysis with beat/miss history, implied moves, and trade plan." />

      <Card title="Upcoming earnings" number={1}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 14 }}>
          {[
            { label: "Quarter", value: data.upcoming.q },
            { label: "EPS estimate", value: `$${data.upcoming.epsEst}` },
            { label: "Rev estimate", value: `$${data.upcoming.revEst}B` },
            { label: "Implied move", value: `±${data.upcoming.impliedMove}%` },
          ].map((m, i) => (
            <div key={i} style={{ padding: 10, borderRadius: 8, background: "rgba(128,128,128,0.04)", textAlign: "center" }}>
              <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>{m.label}</div>
              <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "'DM Mono', monospace" }}>{m.value}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Beat / miss history (last 4Q)" number={2}>
        <div style={{ marginBottom: 8, fontSize: 12 }}>Track record: <span style={{ fontWeight: 600, color: "#0F6E56" }}>{beatCount}/4 beats</span></div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid rgba(128,128,128,0.15)" }}>
              {["Quarter","EPS Est","EPS Actual","Result","Rev Est","Rev Actual","Reaction"].map(h => (
                <th key={h} style={{ padding: "5px 4px", textAlign: "right", fontWeight: 600, fontSize: 10, color: "rgba(128,128,128,0.5)", textTransform: "uppercase" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.quarters.map((q, i) => (
              <tr key={i} style={{ borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
                <td style={{ padding: "6px 4px", fontWeight: 500 }}>{q.q}</td>
                <td style={{ padding: "6px 4px", textAlign: "right", fontFamily: "'DM Mono', monospace" }}>${q.epsEst}</td>
                <td style={{ padding: "6px 4px", textAlign: "right", fontFamily: "'DM Mono', monospace" }}>${q.epsActual}</td>
                <td style={{ padding: "6px 4px", textAlign: "right" }}>
                  <span style={{ padding: "2px 6px", borderRadius: 6, fontSize: 9, fontWeight: 600,
                    background: q.epsActual >= q.epsEst ? "#E1F5EE" : "#FCEBEB",
                    color: q.epsActual >= q.epsEst ? "#0F6E56" : "#A32D2D",
                  }}>{q.epsActual >= q.epsEst ? "BEAT" : "MISS"}</span>
                </td>
                <td style={{ padding: "6px 4px", textAlign: "right", fontFamily: "'DM Mono', monospace" }}>${q.revEst}B</td>
                <td style={{ padding: "6px 4px", textAlign: "right", fontFamily: "'DM Mono', monospace" }}>${q.revActual}B</td>
                <td style={{ padding: "6px 4px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: q.reaction >= 0 ? "#0F6E56" : "#A32D2D" }}>
                  {q.reaction >= 0 ? "+" : ""}{q.reaction}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Revenue segments" number={3}>
        {data.segments.map((seg, i) => (
          <div key={i} style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
              <span>{seg.name}</span>
              <span style={{ display: "flex", gap: 8 }}>
                <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 6,
                  background: seg.trend === "growing" ? "#E1F5EE" : seg.trend === "declining" ? "#FCEBEB" : "rgba(128,128,128,0.08)",
                  color: seg.trend === "growing" ? "#0F6E56" : seg.trend === "declining" ? "#A32D2D" : "rgba(128,128,128,0.5)",
                }}>{seg.trend}</span>
                <span style={{ fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>{seg.pct}%</span>
              </span>
            </div>
            <div style={{ height: 5, borderRadius: 3, background: "rgba(128,128,128,0.1)", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${seg.pct}%`, borderRadius: 3, background: "#0F6E56", transition: "width 0.3s" }} />
            </div>
          </div>
        ))}
      </Card>

      <Card title="Key metrics to watch" number={4}>
        {data.keyMetrics.map((m, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
            <div style={{ width: 18, height: 18, borderRadius: 5, background: "#E1F5EE", color: "#0F6E56", fontSize: 10, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center" }}>{i + 1}</div>
            <span style={{ fontSize: 12 }}>{m}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #5 — BLACKROCK PORTFOLIO CONSTRUCTION
// ═══════════════════════════════════════════

function BlackRockPortfolio({ onBack }) {
  const [profile, setProfile] = useState({ riskTolerance: "moderate", horizon: "10+", accountType: "taxable", monthlyInvest: 2000 });
  const [alloc, setAlloc] = useState([
    { asset: "US Large Cap", ticker: "VTI", pct: 30, type: "core", expReturn: 10.2 },
    { asset: "US Mid/Small Cap", ticker: "VXF", pct: 10, type: "satellite", expReturn: 11.5 },
    { asset: "International Dev.", ticker: "VXUS", pct: 15, type: "core", expReturn: 8.5 },
    { asset: "Emerging Markets", ticker: "VWO", pct: 5, type: "satellite", expReturn: 9.8 },
    { asset: "US Aggregate Bonds", ticker: "BND", pct: 15, type: "core", expReturn: 4.5 },
    { asset: "TIPS", ticker: "VTIP", pct: 5, type: "satellite", expReturn: 3.8 },
    { asset: "REITs", ticker: "VNQ", pct: 8, type: "satellite", expReturn: 8.0 },
    { asset: "Commodities", ticker: "PDBC", pct: 5, type: "satellite", expReturn: 6.5 },
    { asset: "Cash / Short-term", ticker: "SGOV", pct: 7, type: "core", expReturn: 4.8 },
  ]);

  const updateAlloc = (i, val) => { const na = [...alloc]; na[i] = { ...na[i], pct: val }; setAlloc(na); };
  const totalPct = alloc.reduce((a, h) => a + h.pct, 0);
  const expReturn = Math.round(alloc.reduce((a, h) => a + (h.pct / 100) * h.expReturn, 0) * 10) / 10;
  const coreAlloc = alloc.filter(a => a.type === "core").reduce((a, h) => a + h.pct, 0);

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#5" name="Portfolio construction model" firm="BlackRock" desc="Build a custom multi-asset portfolio with ETF picks and allocation rules." />

      <Card title="Investor profile" number={1}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <span style={{ fontSize: 11, fontWeight: 500, display: "block", marginBottom: 4 }}>Risk tolerance</span>
            <OptionPills value={profile.riskTolerance} options={["conservative", "moderate", "aggressive"]} onChange={v => setProfile(p => ({...p, riskTolerance: v}))} />
          </div>
          <div>
            <span style={{ fontSize: 11, fontWeight: 500, display: "block", marginBottom: 4 }}>Time horizon</span>
            <OptionPills value={profile.horizon} options={["1-3 years", "3-10 years", "10+"]} onChange={v => setProfile(p => ({...p, horizon: v}))} />
          </div>
          <div>
            <span style={{ fontSize: 11, fontWeight: 500, display: "block", marginBottom: 4 }}>Account type</span>
            <OptionPills value={profile.accountType} options={["taxable", "IRA/401k", "Roth"]} onChange={v => setProfile(p => ({...p, accountType: v}))} />
          </div>
          <div>
            <span style={{ fontSize: 11, fontWeight: 500, display: "block", marginBottom: 4 }}>Monthly investment ($)</span>
            <input type="number" value={profile.monthlyInvest} step={100} onChange={e => setProfile(p => ({...p, monthlyInvest: parseFloat(e.target.value) || 0}))}
              style={{ width: "100%", padding: "6px 8px", fontSize: 12, fontFamily: "'DM Mono', monospace", border: "1px solid rgba(128,128,128,0.2)", borderRadius: 6, background: "transparent", color: "inherit" }} />
          </div>
        </div>
      </Card>

      <Card title="Asset allocation" number={2}>
        {alloc.map((a, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 0", borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
            <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 4, fontWeight: 600,
              background: a.type === "core" ? "#E1F5EE" : "#EEEDFE",
              color: a.type === "core" ? "#0F6E56" : "#534AB7",
            }}>{a.type}</span>
            <span style={{ fontSize: 12, flex: 1 }}>{a.asset}</span>
            <span style={{ fontSize: 10, fontFamily: "'DM Mono', monospace", color: "rgba(128,128,128,0.5)", width: 40 }}>{a.ticker}</span>
            <input type="number" value={a.pct} min={0} max={100} onChange={e => updateAlloc(i, parseFloat(e.target.value) || 0)}
              style={{ width: 44, textAlign: "center", padding: "3px", fontSize: 11, fontFamily: "'DM Mono', monospace", border: "1px solid rgba(128,128,128,0.2)", borderRadius: 5, background: "transparent", color: "inherit" }} />
            <span style={{ fontSize: 10, color: "rgba(128,128,128,0.4)" }}>%</span>
          </div>
        ))}
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10, fontSize: 12 }}>
          <span>Core: {coreAlloc}% · Satellite: {totalPct - coreAlloc}%</span>
          <span style={{ fontWeight: 600, color: Math.abs(totalPct - 100) > 0.1 ? "#A32D2D" : "#0F6E56" }}>Total: {totalPct}%</span>
        </div>
      </Card>

      <Card title="Expected performance" number={3}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
          <div style={{ padding: 12, borderRadius: 10, background: "#E1F5EE", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>Expected annual return</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>{expReturn}%</div>
          </div>
          <div style={{ padding: 12, borderRadius: 10, background: "#FAEEDA", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>DCA monthly</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#BA7517" }}>${profile.monthlyInvest.toLocaleString()}</div>
          </div>
          <div style={{ padding: 12, borderRadius: 10, background: "#E6F1FB", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)", marginBottom: 2 }}>10-year projection</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#185FA5" }}>
              ${Math.round(profile.monthlyInvest * 12 * ((Math.pow(1 + expReturn / 100, 10) - 1) / (expReturn / 100))).toLocaleString()}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #6 — CITADEL TECHNICAL ANALYSIS
// ═══════════════════════════════════════════

function CitadelTechnical({ onBack }) {
  const [s, set] = useState({
    ticker: "AAPL", price: 195, ma50: 188, ma100: 182, ma200: 175,
    rsi: 62, macdSignal: "bullish", bbPosition: "middle",
    support1: 185, support2: 175, resistance1: 205, resistance2: 215,
    volume: "increasing", pattern: "ascending_triangle",
    trend: { daily: "bullish", weekly: "bullish", monthly: "neutral" },
    fib382: 182, fib500: 178, fib618: 174,
  });
  const u = (k, v) => set(p => ({ ...p, [k]: v }));

  const rr = Math.abs(s.resistance1 - s.price) > 0 ? Math.round(Math.abs(s.resistance1 - s.price) / Math.abs(s.price - s.support1) * 10) / 10 : 0;
  const trendScore = [s.trend.daily, s.trend.weekly, s.trend.monthly].filter(t => t === "bullish").length;
  const signal = trendScore >= 2 && s.rsi < 70 && s.macdSignal === "bullish" ? "Buy" : trendScore === 0 || s.rsi > 75 ? "Sell" : "Neutral";
  const signalColor = signal === "Buy" ? "#0F6E56" : signal === "Sell" ? "#A32D2D" : "#BA7517";

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#6" name="Technical analysis system" firm="Citadel" desc="Multi-timeframe technical analysis with indicators, patterns, and trade plan." />

      <Card title="Price & moving averages" number={1}>
        <Slider label="Current price" value={s.price} onChange={v => u("price", v)} min={50} max={500} step={1} suffix="" />
        <Slider label="50-day MA" value={s.ma50} onChange={v => u("ma50", v)} min={50} max={500} step={1} suffix="" />
        <Slider label="200-day MA" value={s.ma200} onChange={v => u("ma200", v)} min={50} max={500} step={1} suffix="" />
        <div style={{ padding: 10, borderRadius: 8, background: s.price > s.ma200 ? "#E1F5EE" : "#FCEBEB", fontSize: 12, textAlign: "center" }}>
          Price {s.price > s.ma200 ? "above" : "below"} 200-day MA — <span style={{ fontWeight: 600, color: s.price > s.ma200 ? "#0F6E56" : "#A32D2D" }}>{s.price > s.ma200 ? "Bullish" : "Bearish"} trend</span>
        </div>
      </Card>

      <Card title="Indicators" number={2}>
        <Slider label="RSI (14)" value={s.rsi} onChange={v => u("rsi", v)} min={0} max={100} step={1} suffix="" desc={s.rsi > 70 ? "Overbought zone" : s.rsi < 30 ? "Oversold zone" : "Neutral zone"} />
        <div style={{ marginBottom: 12 }}>
          <span style={{ fontSize: 12, fontWeight: 500, display: "block", marginBottom: 6 }}>MACD signal</span>
          <OptionPills value={s.macdSignal} options={["bullish", "neutral", "bearish"]} onChange={v => u("macdSignal", v)} />
        </div>
        <div>
          <span style={{ fontSize: 12, fontWeight: 500, display: "block", marginBottom: 6 }}>Bollinger Band position</span>
          <OptionPills value={s.bbPosition} options={["upper", "middle", "lower"]} onChange={v => u("bbPosition", v)} />
        </div>
      </Card>

      <Card title="Trend direction" number={3}>
        {["daily", "weekly", "monthly"].map(tf => (
          <div key={tf} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0", borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
            <span style={{ fontSize: 12, fontWeight: 500, width: 70, textTransform: "capitalize" }}>{tf}</span>
            <OptionPills value={s.trend[tf]} options={["bullish", "neutral", "bearish"]} onChange={v => set(p => ({...p, trend: {...p.trend, [tf]: v}}))} />
          </div>
        ))}
      </Card>

      <Card title="Support & resistance" number={4}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <Slider label="Support 1" value={s.support1} onChange={v => u("support1", v)} min={50} max={500} step={1} suffix="" />
          <Slider label="Resistance 1" value={s.resistance1} onChange={v => u("resistance1", v)} min={50} max={500} step={1} suffix="" />
        </div>
      </Card>

      <Card title="Trade plan" number={5} accent={signalColor}>
        <div style={{ padding: 14, borderRadius: 10, background: signalColor, color: "#fff", textAlign: "center", marginBottom: 14 }}>
          <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.06em", opacity: 0.7, marginBottom: 4 }}>Signal</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{signal}</div>
          <div style={{ fontSize: 11, marginTop: 4, opacity: 0.8 }}>Confidence: {trendScore >= 2 ? "High" : trendScore >= 1 ? "Medium" : "Low"} · R:R = {rr}:1</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
          <div style={{ padding: 10, borderRadius: 8, background: "#E1F5EE", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>Entry zone</div>
            <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>${s.support1}-{s.price}</div>
          </div>
          <div style={{ padding: 10, borderRadius: 8, background: "#FCEBEB", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>Stop loss</div>
            <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "'DM Mono', monospace", color: "#A32D2D" }}>${s.support1 - 5}</div>
          </div>
          <div style={{ padding: 10, borderRadius: 8, background: "#E6F1FB", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>Target</div>
            <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "'DM Mono', monospace", color: "#185FA5" }}>${s.resistance1}</div>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #7 — HARVARD DIVIDEND STRATEGY
// ═══════════════════════════════════════════

function HarvardDividend({ onBack }) {
  const [investAmt, setInvestAmt] = useState(100000);
  const [stocks] = useState([
    { ticker: "JNJ", name: "Johnson & Johnson", yield: 2.95, safety: 9, consYears: 62, payout: 46, growth5y: 5.8, sector: "Healthcare" },
    { ticker: "PG", name: "Procter & Gamble", yield: 2.41, safety: 9, consYears: 68, payout: 58, growth5y: 5.5, sector: "Cons. staples" },
    { ticker: "KO", name: "Coca-Cola", yield: 3.05, safety: 8, consYears: 62, payout: 71, growth5y: 3.8, sector: "Cons. staples" },
    { ticker: "PEP", name: "PepsiCo", yield: 2.72, safety: 8, consYears: 52, payout: 67, growth5y: 7.1, sector: "Cons. staples" },
    { ticker: "O", name: "Realty Income", yield: 5.45, safety: 7, consYears: 28, payout: 75, growth5y: 3.2, sector: "REITs" },
    { ticker: "XOM", name: "Exxon Mobil", yield: 3.35, safety: 7, consYears: 41, payout: 44, growth5y: 2.1, sector: "Energy" },
    { ticker: "ABBV", name: "AbbVie", yield: 3.52, safety: 7, consYears: 52, payout: 52, growth5y: 8.3, sector: "Healthcare" },
    { ticker: "MCD", name: "McDonald's", yield: 2.25, safety: 8, consYears: 48, payout: 57, growth5y: 8.0, sector: "Cons. disc." },
    { ticker: "T", name: "AT&T", yield: 6.52, safety: 5, consYears: 0, payout: 66, growth5y: -1.2, sector: "Telecom" },
    { ticker: "VZ", name: "Verizon", yield: 6.38, safety: 6, consYears: 19, payout: 57, growth5y: 2.0, sector: "Telecom" },
  ]);

  const avgYield = Math.round(stocks.reduce((a, s) => a + s.yield, 0) / stocks.length * 100) / 100;
  const annualIncome = Math.round(investAmt * avgYield / 100);
  const monthlyIncome = Math.round(annualIncome / 12);

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#7" name="Dividend income strategy" firm="Harvard Endowment" desc="Build a dividend portfolio with safety scores, DRIP projections, and income estimates." />

      <Card title="Investment amount" number={1}>
        <Slider label="Total investment" value={investAmt} onChange={setInvestAmt} min={10000} max={1000000} step={5000} suffix="" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginTop: 8 }}>
          <div style={{ padding: 10, borderRadius: 8, background: "#E1F5EE", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>Avg portfolio yield</div>
            <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>{avgYield}%</div>
          </div>
          <div style={{ padding: 10, borderRadius: 8, background: "#E6F1FB", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>Annual income</div>
            <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#185FA5" }}>${annualIncome.toLocaleString()}</div>
          </div>
          <div style={{ padding: 10, borderRadius: 8, background: "#FAEEDA", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>Monthly income</div>
            <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#BA7517" }}>${monthlyIncome.toLocaleString()}</div>
          </div>
        </div>
      </Card>

      <Card title="Dividend stock picks" number={2}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid rgba(128,128,128,0.15)" }}>
                {["Ticker","Yield","Safety","Consec. Yrs","Payout","Growth","Sector"].map(h => (
                  <th key={h} style={{ padding: "5px 4px", textAlign: "left", fontWeight: 600, fontSize: 10, color: "rgba(128,128,128,0.5)", textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...stocks].sort((a, b) => b.safety - a.safety).map(s => (
                <tr key={s.ticker} style={{ borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
                  <td style={{ padding: "6px 4px" }}><span style={{ fontWeight: 600, fontFamily: "'DM Mono', monospace" }}>{s.ticker}</span><br/><span style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>{s.name}</span></td>
                  <td style={{ padding: "6px 4px", fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>{s.yield}%</td>
                  <td style={{ padding: "6px 4px" }}><span style={{ fontWeight: 600, color: s.safety >= 8 ? "#0F6E56" : s.safety >= 6 ? "#BA7517" : "#A32D2D" }}>{s.safety}/10</span></td>
                  <td style={{ padding: "6px 4px", fontFamily: "'DM Mono', monospace" }}>{s.consYears || "—"}</td>
                  <td style={{ padding: "6px 4px", fontFamily: "'DM Mono', monospace", color: s.payout > 70 ? "#A32D2D" : "inherit" }}>{s.payout}%</td>
                  <td style={{ padding: "6px 4px", fontFamily: "'DM Mono', monospace", color: s.growth5y > 0 ? "#0F6E56" : "#A32D2D" }}>{s.growth5y > 0 ? "+" : ""}{s.growth5y}%</td>
                  <td style={{ padding: "6px 4px", fontSize: 10, color: "rgba(128,128,128,0.5)" }}>{s.sector}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="10-year DRIP projection" number={3}>
        <div style={{ fontSize: 12, color: "rgba(128,128,128,0.6)", marginBottom: 10 }}>Assumes {avgYield}% yield with 5% annual dividend growth, reinvested.</div>
        {[1, 3, 5, 7, 10].map(yr => {
          const val = Math.round(investAmt * Math.pow(1 + (avgYield + 5) / 100, yr));
          const inc = Math.round(val * avgYield / 100);
          return (
            <div key={yr} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
              <span style={{ fontSize: 11, fontWeight: 600, width: 55 }}>Year {yr}</span>
              <div style={{ flex: 1, height: 6, borderRadius: 3, background: "rgba(128,128,128,0.1)", overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${Math.min((val / (investAmt * 3)) * 100, 100)}%`, borderRadius: 3, background: "#0F6E56" }} />
              </div>
              <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, width: 80, textAlign: "right" }}>${val.toLocaleString()}</span>
              <span style={{ fontSize: 10, color: "rgba(128,128,128,0.5)", width: 70, textAlign: "right" }}>${inc.toLocaleString()}/yr</span>
            </div>
          );
        })}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #8 — BAIN COMPETITIVE ANALYSIS
// ═══════════════════════════════════════════

function BainCompetitive({ onBack }) {
  const [sector] = useState("Cloud Infrastructure");
  const [companies] = useState([
    { name: "Amazon (AWS)", mktCap: "2.1T", revenue: 90.8, margin: 30.2, share: 31, moat: "Scale + switching", mgmt: 9, rd: 12.5, trend: "stable" },
    { name: "Microsoft (Azure)", mktCap: "3.1T", revenue: 65.1, margin: 42.5, share: 24, moat: "Ecosystem + switching", mgmt: 10, rd: 15.2, trend: "growing" },
    { name: "Google (GCP)", mktCap: "2.2T", revenue: 37.5, margin: 17.8, share: 11, moat: "AI/Data + scale", mgmt: 8, rd: 18.1, trend: "growing" },
    { name: "Oracle Cloud", mktCap: "390B", revenue: 19.8, margin: 25.3, share: 5, moat: "Database switching", mgmt: 7, rd: 8.2, trend: "growing" },
    { name: "IBM Cloud", mktCap: "195B", revenue: 13.2, margin: 18.1, share: 3, moat: "Enterprise legacy", mgmt: 6, rd: 6.5, trend: "declining" },
  ]);

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#8" name="Competitive advantage analysis" firm="Bain & Company" desc={`Competitive landscape for ${sector}: moats, margins, market share, best pick.`} />

      <Card title="Market overview" number={1}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid rgba(128,128,128,0.15)" }}>
              {["Company","Mkt Cap","Rev ($B)","Margin","Share","R&D %","Trend"].map(h => (
                <th key={h} style={{ padding: "5px 4px", textAlign: "left", fontWeight: 600, fontSize: 10, color: "rgba(128,128,128,0.5)", textTransform: "uppercase" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {companies.map(c => (
              <tr key={c.name} style={{ borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
                <td style={{ padding: "6px 4px", fontWeight: 600, fontSize: 12 }}>{c.name}</td>
                <td style={{ padding: "6px 4px", fontFamily: "'DM Mono', monospace" }}>{c.mktCap}</td>
                <td style={{ padding: "6px 4px", fontFamily: "'DM Mono', monospace" }}>{c.revenue}</td>
                <td style={{ padding: "6px 4px", fontFamily: "'DM Mono', monospace", color: c.margin > 30 ? "#0F6E56" : "inherit" }}>{c.margin}%</td>
                <td style={{ padding: "6px 4px", fontFamily: "'DM Mono', monospace" }}>{c.share}%</td>
                <td style={{ padding: "6px 4px", fontFamily: "'DM Mono', monospace" }}>{c.rd}%</td>
                <td style={{ padding: "6px 4px" }}><span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 6,
                  background: c.trend === "growing" ? "#E1F5EE" : c.trend === "declining" ? "#FCEBEB" : "rgba(128,128,128,0.08)",
                  color: c.trend === "growing" ? "#0F6E56" : c.trend === "declining" ? "#A32D2D" : "rgba(128,128,128,0.5)",
                }}>{c.trend}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Competitive moat analysis" number={2}>
        {companies.map(c => (
          <div key={c.name} style={{ padding: "8px 0", borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600 }}>{c.name}</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: "#0F6E56" }}>{c.mgmt}/10</span>
            </div>
            <span style={{ fontSize: 11, color: "rgba(128,128,128,0.5)" }}>Moat: {c.moat}</span>
          </div>
        ))}
      </Card>

      <Card title="Best pick recommendation" number={3} accent="#0F6E56">
        <div style={{ padding: 14, borderRadius: 10, background: "#0F6E56", color: "#fff" }}>
          <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.06em", opacity: 0.7, marginBottom: 4 }}>Top pick</div>
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 6 }}>Microsoft (Azure)</div>
          <div style={{ fontSize: 12, opacity: 0.85, lineHeight: 1.6 }}>
            Strongest ecosystem moat with Office 365/Teams integration driving cloud adoption. Highest margins in the group at 42.5%.
            AI integration via OpenAI partnership creates an additional growth catalyst. Growing share in a $600B+ TAM.
          </div>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// FRAMEWORK #9 — RENAISSANCE PATTERN FINDER
// ═══════════════════════════════════════════

function RenaissancePatterns({ onBack }) {
  const [data] = useState({
    seasonal: [
      { month: "Jan", avgReturn: 2.1 }, { month: "Feb", avgReturn: -0.3 }, { month: "Mar", avgReturn: 1.5 },
      { month: "Apr", avgReturn: 3.2 }, { month: "May", avgReturn: 0.8 }, { month: "Jun", avgReturn: -1.2 },
      { month: "Jul", avgReturn: 2.8 }, { month: "Aug", avgReturn: -0.5 }, { month: "Sep", avgReturn: -2.1 },
      { month: "Oct", avgReturn: 1.9 }, { month: "Nov", avgReturn: 3.5 }, { month: "Dec", avgReturn: 2.4 },
    ],
    insiders: { buying: 12, selling: 3, netDirection: "Buying", ratio: 4.0 },
    institutional: { ownership: 72.5, changeQ: +1.8, topBuyers: ["Vanguard", "BlackRock", "State Street"], topSellers: ["Renaissance", "DE Shaw"] },
    shortInterest: { pct: 2.8, daysTocover: 1.5, change: -0.5, squeezeRisk: "Low" },
    correlations: [
      { event: "Fed rate decision", corr: 0.72, direction: "Positive" },
      { event: "CPI release", corr: -0.45, direction: "Inverse" },
      { event: "Earnings season", corr: 0.88, direction: "Positive" },
      { event: "VIX spike (>25)", corr: -0.65, direction: "Inverse" },
    ],
  });

  return (
    <div>
      <BackButton onClick={onBack} />
      <FrameworkHeader num="#9" name="Quantitative pattern finder" firm="Renaissance Technologies" desc="Statistical edges: seasonal patterns, insider flow, correlations, anomalies." />

      <Card title="Seasonal performance" number={1}>
        <div style={{ display: "flex", gap: 3, alignItems: "flex-end", height: 120, marginBottom: 8 }}>
          {data.seasonal.map((m, i) => {
            const maxAbs = Math.max(...data.seasonal.map(s => Math.abs(s.avgReturn)));
            const h = Math.abs(m.avgReturn) / maxAbs * 80;
            return (
              <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", height: "100%" }}>
                <span style={{ fontSize: 9, fontFamily: "'DM Mono', monospace", color: m.avgReturn >= 0 ? "#0F6E56" : "#A32D2D", marginBottom: 2 }}>
                  {m.avgReturn > 0 ? "+" : ""}{m.avgReturn}
                </span>
                <div style={{
                  width: "100%", height: h, borderRadius: "3px 3px 0 0",
                  background: m.avgReturn >= 0 ? "#0F6E56" : "#A32D2D", opacity: 0.7,
                }} />
                <span style={{ fontSize: 8, color: "rgba(128,128,128,0.5)", marginTop: 2 }}>{m.month}</span>
              </div>
            );
          })}
        </div>
        <div style={{ fontSize: 11, color: "rgba(128,128,128,0.5)" }}>Best months: Nov (+3.5%), Apr (+3.2%). Worst: Sep (-2.1%)</div>
      </Card>

      <Card title="Insider activity" number={2}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 12 }}>
          <div style={{ padding: 10, borderRadius: 8, background: "#E1F5EE", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>Buy transactions</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#0F6E56" }}>{data.insiders.buying}</div>
          </div>
          <div style={{ padding: 10, borderRadius: 8, background: "#FCEBEB", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>Sell transactions</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#A32D2D" }}>{data.insiders.selling}</div>
          </div>
          <div style={{ padding: 10, borderRadius: 8, background: "#E6F1FB", textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "rgba(128,128,128,0.5)" }}>Buy/sell ratio</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#185FA5" }}>{data.insiders.ratio}x</div>
          </div>
        </div>
        <InfoBox>Strong insider buying signal — {data.insiders.buying} buys vs {data.insiders.selling} sells. Ratio of {data.insiders.ratio}x is bullish.</InfoBox>
      </Card>

      <Card title="Event correlations" number={3}>
        {data.correlations.map((c, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0", borderBottom: "1px solid rgba(128,128,128,0.06)" }}>
            <span style={{ fontSize: 12, flex: 1 }}>{c.event}</span>
            <span style={{ fontSize: 9, padding: "2px 8px", borderRadius: 6,
              background: c.direction === "Positive" ? "#E1F5EE" : "#FCEBEB",
              color: c.direction === "Positive" ? "#0F6E56" : "#A32D2D",
            }}>{c.direction}</span>
            <span style={{ fontSize: 12, fontWeight: 600, fontFamily: "'DM Mono', monospace", width: 40, textAlign: "right" }}>{c.corr}</span>
          </div>
        ))}
      </Card>

      <Card title="Short interest" number={4}>
        <MetricRow label="Short interest" value={`${data.shortInterest.pct}%`} />
        <MetricRow label="Days to cover" value={data.shortInterest.daysTocover} />
        <MetricRow label="Monthly change" value={`${data.shortInterest.change > 0 ? "+" : ""}${data.shortInterest.change}%`} color={data.shortInterest.change < 0 ? "#0F6E56" : "#A32D2D"} />
        <MetricRow label="Squeeze potential" value={data.shortInterest.squeezeRisk} color={data.shortInterest.squeezeRisk === "High" ? "#A32D2D" : "#0F6E56"} />
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// LANDING PAGE
// ═══════════════════════════════════════════

function LandingPage({ onNavigate }) {
  const [hovered, setHovered] = useState(null);
  const [anim, setAnim] = useState(false);
  useEffect(() => { setTimeout(() => setAnim(true), 50); }, []);

  return (
    <div style={{ minHeight: "100vh" }}>
      {/* Hero */}
      <div style={{
        textAlign: "center", padding: "48px 20px 36px",
        opacity: anim ? 1 : 0, transform: anim ? "translateY(0)" : "translateY(20px)",
        transition: "all 0.6s cubic-bezier(0.16,1,0.3,1)",
      }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 16, padding: "5px 14px", borderRadius: 20, border: "1px solid rgba(128,128,128,0.15)", fontSize: 11, fontWeight: 500, color: "rgba(128,128,128,0.5)" }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#0F6E56" }} />
          10 frameworks · 4 layers · 1 system
        </div>
        <h1 style={{ fontSize: 36, fontWeight: 700, letterSpacing: "-0.04em", margin: "0 0 10px", lineHeight: 1.1 }}>
          Analytical<br/>command center
        </h1>
        <p style={{ fontSize: 14, color: "rgba(128,128,128,0.5)", maxWidth: 440, margin: "0 auto", lineHeight: 1.6 }}>
          Wall Street-grade analytical frameworks unified in a single platform.
          Navigate the 4-layer decision system from macro to execution.
        </p>
      </div>

      {/* Layer sections */}
      {LAYERS.map((layer, li) => {
        const layerFrameworks = FRAMEWORKS.filter(f => f.layer === layer.id);
        return (
          <div key={layer.id} style={{
            marginBottom: 28, padding: "0 4px",
            opacity: anim ? 1 : 0, transform: anim ? "translateY(0)" : "translateY(30px)",
            transition: `all 0.6s cubic-bezier(0.16,1,0.3,1) ${0.15 + li * 0.1}s`,
          }}>
            {/* Layer header */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 13, fontWeight: 700, background: layer.bg, color: layer.color,
              }}>{layer.id}</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.02em" }}>{layer.title}</div>
                <div style={{ fontSize: 11, color: "rgba(128,128,128,0.5)", fontStyle: "italic" }}>{layer.question}</div>
              </div>
            </div>

            {/* Framework cards */}
            <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(layerFrameworks.length, 4)}, 1fr)`, gap: 8, paddingLeft: 38 }}>
              {layerFrameworks.map((fw) => (
                <button
                  key={fw.id}
                  onClick={() => onNavigate(fw.id)}
                  onMouseEnter={() => setHovered(fw.id)}
                  onMouseLeave={() => setHovered(null)}
                  style={{
                    textAlign: "left", padding: "16px 14px 14px", borderRadius: 12, cursor: "pointer",
                    fontFamily: "inherit", transition: "all 0.2s cubic-bezier(0.16,1,0.3,1)",
                    border: hovered === fw.id ? `1.5px solid ${layer.color}` : "1px solid rgba(128,128,128,0.12)",
                    background: hovered === fw.id ? layer.bg : "var(--color-background-primary, #fff)",
                    transform: hovered === fw.id ? "translateY(-2px)" : "none",
                  }}
                >
                  <div style={{
                    fontSize: 10, fontWeight: 600, marginBottom: 6, padding: "2px 8px", borderRadius: 6,
                    display: "inline-block", background: layer.bg, color: layer.color,
                  }}>{fw.num}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, letterSpacing: "-0.01em", color: "var(--color-text-primary, #1a1a1a)" }}>{fw.name}</div>
                  <div style={{ fontSize: 11, color: "rgba(128,128,128,0.5)", lineHeight: 1.5 }}>{fw.desc}</div>
                  <div style={{ fontSize: 10, fontWeight: 500, color: layer.color, marginTop: 8, display: "flex", alignItems: "center", gap: 4 }}>
                    Open framework <span style={{ fontSize: 12 }}>→</span>
                  </div>
                </button>
              ))}
            </div>

            {/* Arrow between layers */}
            {li < LAYERS.length - 1 && (
              <div style={{ display: "flex", justifyContent: "center", padding: "8px 0 4px" }}>
                <svg width="16" height="16" viewBox="0 0 16 16"><path d="M8 3L8 11M5 9L8 12L11 9" fill="none" stroke="rgba(128,128,128,0.25)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </div>
            )}
          </div>
        );
      })}

      {/* Footer */}
      <div style={{ textAlign: "center", padding: "24px 0 40px", fontSize: 11, color: "rgba(128,128,128,0.35)" }}>
        Analytical command center · 10 frameworks · Built for reuse
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════
// ROOT APP — ROUTER
// ═══════════════════════════════════════════

const FRAMEWORK_MAP = {
  1: GoldmanScreener,
  2: MorganStanleyDCF,
  3: BridgewaterRisk,
  4: JPMorganEarnings,
  5: BlackRockPortfolio,
  6: CitadelTechnical,
  7: HarvardDividend,
  8: BainCompetitive,
  9: RenaissancePatterns,
  10: McKinseyMacro,
};

export default function App() {
  const [page, setPage] = useState(null);

  const goHome = () => { setPage(null); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const goTo = (id) => { setPage(id); window.scrollTo({ top: 0 }); };

  const FrameworkComponent = page ? FRAMEWORK_MAP[page] : null;

  return (
    <div style={{
      fontFamily: "'Instrument Sans', 'SF Pro Display', -apple-system, sans-serif",
      maxWidth: 780, margin: "0 auto", padding: "0 12px",
      color: "var(--color-text-primary, #1a1a1a)", lineHeight: 1.5,
    }}>
      <link href={FONTS_LINK} rel="stylesheet" />
      {!page && <LandingPage onNavigate={goTo} />}
      {FrameworkComponent && <div style={{ paddingTop: 20 }}><FrameworkComponent onBack={goHome} /></div>}
    </div>
  );
}
