"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

/* ============================================================
   MARKETING LANDING PAGE — Underwrite AI
   Ported from the Claude Design handoff
   ("Underwriting Landing.dc.html"). Public front door for the
   Financial Underwriting AI platform.
   ============================================================ */

const MONO = "var(--font-mono)";
const SERIF_DISPLAY = "var(--font-playfair)";
const SERIF_READER = "var(--font-newsreader)";

const navLink: CSSProperties = {
  fontSize: 14,
  color: "#475569",
  textDecoration: "none",
  fontWeight: 500,
};

const sectionEyebrow: CSSProperties = {
  fontSize: 12,
  textTransform: "uppercase",
  letterSpacing: "0.1em",
  color: "#F97316",
  fontWeight: 700,
  marginBottom: 16,
};

const footerLink: CSSProperties = {
  fontSize: 14,
  color: "#94A3B8",
  textDecoration: "none",
  fontWeight: 500,
};

const dealFiles = [
  { name: "Offering Memorandum", pages: "88p" },
  { name: "T12 Operating Statement", pages: "12p" },
  { name: "Rent Roll", pages: "6p" },
  { name: "P&L Summary", pages: "9p" },
];

const expenseMap = [
  { raw: "R&M Plumbing", to: "Repairs & Maint.", tone: "ok" as const },
  { raw: "Mgmt Fee", to: "Management", tone: "ok" as const },
  { raw: "Trash Removal", to: "Duplicate removed", tone: "dropped" as const },
];

const summaryStats = [
  { label: "Going In IRR", value: "18.2%", color: "#16A34A" },
  { label: "MOIC", value: "2.14x", color: "#0F172A" },
  { label: "Cash on Cash", value: "7.8%", color: "#0F172A" },
  { label: "DSCR", value: "1.42x", color: "#0F172A" },
  { label: "Exit Cap", value: "6.00%", color: "#0F172A" },
  { label: "Occupancy", value: "93.5%", color: "#0F172A" },
];

const modelSteps = [
  { n: "01", title: "Revenue", sub: "Gross Potential Rent → Loss to Lease → Vacancy → EGI", val: "$4.21M", valColor: "#fff" },
  { n: "02", title: "Expenses", sub: "Normalized, deduplicated, taxes & mgmt fees recomputed", val: "−$1.87M", valColor: "#F87171" },
  { n: "03", title: "Net Operating Income", sub: "EGI less Expenses · Entry Cap = NOI / Price", val: "$2.34M", valColor: "#4ADE80" },
  { n: "04", title: "Debt Service", sub: "Pretax cash flow = NOI less annual debt service", val: "1.42x DSCR", valColor: "#fff" },
];

const features = [
  {
    title: "Zero hallucination OCR",
    body: "Vision extraction tuned to faithfully digitize, never embellish. Large files chunk automatically, and dense statements process page accurately.",
    icon: <div style={{ width: 13, height: 13, border: "2.5px solid #F97316", borderRadius: 3 }} />,
  },
  {
    title: "Expense normalization",
    body: "Every raw line maps to a standard category, with duplicates caught and conflicting source documents reconciled by priority: OM over T12 over raw bills.",
    icon: <div style={{ width: 13, height: 13, border: "2.5px solid #F97316", borderRadius: 9999 }} />,
  },
  {
    title: "Deterministic engine",
    body: "The five step model is fixed code, not a prompt. Same inputs, same outputs, including the 38% expense ratio floor and reserve logic.",
    icon: <div style={{ width: 13, height: 13, border: "2.5px solid #F97316", transform: "rotate(45deg)" }} />,
  },
  {
    title: "Sensitivity analysis",
    body: "Flex rent growth, vacancy, exit cap and rate in real time. Watch IRR and NOI move across a live heat map before you commit.",
    icon: (
      <div style={{ display: "flex", gap: 2.5, alignItems: "flex-end" }}>
        <div style={{ width: 3, height: 7, background: "#F97316" }} />
        <div style={{ width: 3, height: 12, background: "#F97316" }} />
        <div style={{ width: 3, height: 9, background: "#F97316" }} />
      </div>
    ),
  },
  {
    title: "Full audit trail",
    body: "Every figure links back to the page and line it came from. Each transformation is logged, so a reviewer can trust the number and trace the why.",
    icon: (
      <div style={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
        <div style={{ width: 14, height: 2.5, background: "#F97316" }} />
        <div style={{ width: 14, height: 2.5, background: "#F97316" }} />
        <div style={{ width: 9, height: 2.5, background: "#F97316" }} />
      </div>
    ),
  },
  {
    title: "One click exports",
    body: "Push the underwriting to a formatted Excel workbook, a PDF due diligence report, or a written investment memo, ready for the IC.",
    icon: <div style={{ width: 8, height: 11, border: "2px solid #F97316", borderRadius: 2 }} />,
  },
];

export default function LandingPage() {
  return (
    <div style={{ position: "relative", overflow: "hidden", background: "#F8FAFC", color: "#0F172A" }}>
      {/* Responsive collapse rules for the landing grids */}
      <style>{`
        @media (max-width: 960px) {
          .uw-hero { grid-template-columns: 1fr !important; }
          .uw-how { grid-template-columns: 1fr !important; }
          .uw-how .uw-connector { display: none !important; }
          .uw-model { grid-template-columns: 1fr !important; }
          .uw-features { grid-template-columns: 1fr 1fr !important; }
          .uw-security { grid-template-columns: 1fr !important; }
          .uw-footer { grid-template-columns: 1fr 1fr !important; }
        }
        @media (max-width: 700px) {
          .uw-nav-links { display: none !important; }
          .uw-features { grid-template-columns: 1fr !important; }
          .uw-footer { grid-template-columns: 1fr !important; }
          .uw-h1 { font-size: 42px !important; }
        }
        .uw-foot-link:hover { color: #fff !important; }
        .uw-nav-link:hover { color: #0F172A !important; }
      `}</style>

      {/* BACKGROUND LAYERS */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          zIndex: 0,
          backgroundImage:
            "linear-gradient(to right, rgba(100,116,139,0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(100,116,139,0.05) 1px, transparent 1px)",
          backgroundSize: "34px 34px",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: -260,
          left: "50%",
          transform: "translateX(-50%)",
          width: 1100,
          height: 720,
          borderRadius: "100%",
          background: "radial-gradient(circle, rgba(249,115,22,0.12) 0%, transparent 62%)",
          filter: "blur(70px)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      />

      {/* NAV */}
      <nav
        style={{
          position: "relative",
          zIndex: 20,
          maxWidth: 1200,
          margin: "0 auto",
          padding: "22px 40px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <BrandMark />
        <div className="uw-nav-links" style={{ display: "flex", alignItems: "center", gap: 34 }}>
          <a href="#how" className="uw-nav-link" style={navLink}>How it works</a>
          <a href="#model" className="uw-nav-link" style={navLink}>The model</a>
          <a href="#features" className="uw-nav-link" style={navLink}>Platform</a>
          <a href="#security" className="uw-nav-link" style={navLink}>Security</a>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Link href="/signin" style={{ fontSize: 14, color: "#0F172A", textDecoration: "none", fontWeight: 600 }}>
            Sign in
          </Link>
          <Link
            href="/signup"
            style={{
              fontSize: 14,
              color: "#fff",
              textDecoration: "none",
              fontWeight: 600,
              background: "#F97316",
              padding: "9px 18px",
              borderRadius: 9,
              boxShadow: "0 4px 14px rgba(249,115,22,0.35)",
            }}
          >
            Request access
          </Link>
        </div>
      </nav>

      {/* HERO */}
      <section
        className="uw-hero"
        style={{
          position: "relative",
          zIndex: 10,
          maxWidth: 1200,
          margin: "0 auto",
          padding: "56px 40px 76px",
          display: "grid",
          gridTemplateColumns: "1.02fr 0.98fr",
          gap: 56,
          alignItems: "center",
        }}
      >
        <div>
          <div
            style={{
              display: "inline-flex",
              gap: 10,
              alignItems: "center",
              border: "1px solid #E2E8F0",
              borderRadius: 9999,
              padding: "6px 13px 6px 11px",
              background: "#fff",
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
              marginBottom: 26,
            }}
          >
            <PingDot />
            <span style={{ fontFamily: SERIF_READER, fontStyle: "italic", color: "#F97316", fontSize: 13, fontWeight: 500 }}>
              Underwrite AI
            </span>
            <span style={{ height: 12, width: 1, background: "#CBD5E1" }} />
            <span style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.08em", color: "#64748B", fontWeight: 600 }}>
              Financial Intelligence
            </span>
          </div>

          <h1 className="uw-h1" style={{ fontSize: 60, lineHeight: 1.04, letterSpacing: "-0.035em", fontWeight: 600, margin: "0 0 22px", color: "#0F172A" }}>
            Underwrite any deal in{" "}
            <span style={{ fontFamily: SERIF_DISPLAY, fontStyle: "italic", fontWeight: 500, color: "#F97316" }}>minutes,</span> not days.
          </h1>
          <p style={{ fontSize: 18.5, lineHeight: 1.6, color: "#475569", margin: "0 0 34px", maxWidth: 520 }}>
            Drop in the OM, T12, rent roll and P&amp;L. The platform reads every page, normalizes the expenses, and runs a defensible
            institutional model, taking NOI to IRR, with every figure traced back to its source.
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 40, flexWrap: "wrap" }}>
            <Link
              href="/signup"
              style={{
                fontSize: 15,
                color: "#fff",
                textDecoration: "none",
                fontWeight: 600,
                background: "#F97316",
                padding: "14px 26px",
                borderRadius: 11,
                boxShadow: "0 6px 20px rgba(249,115,22,0.38)",
              }}
            >
              Request access
            </Link>
            <a
              href="#how"
              style={{
                fontSize: 15,
                color: "#0F172A",
                textDecoration: "none",
                fontWeight: 600,
                padding: "14px 22px",
                borderRadius: 11,
                border: "1px solid #CBD5E1",
                background: "#fff",
              }}
            >
              See how it works
            </a>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 28, flexWrap: "wrap" }}>
            <HeroStat value="3 min" label="avg. deal turnaround" />
            <div style={{ height: 34, width: 1, background: "#E2E8F0" }} />
            <HeroStat value="100%" label="figures traced to source" />
            <div style={{ height: 34, width: 1, background: "#E2E8F0" }} />
            <HeroStat value="5 step" label="deterministic model" />
          </div>
        </div>

        {/* HERO PRODUCT CARD */}
        <div style={{ position: "relative" }}>
          <div
            style={{
              position: "absolute",
              top: -22,
              right: 14,
              zIndex: 3,
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              background: "#fff",
              border: "1px solid #E2E8F0",
              borderRadius: 9999,
              padding: "7px 13px",
              boxShadow: "0 8px 24px rgba(0,0,0,0.10)",
              animation: "uw_float 5s ease-in-out infinite",
            }}
          >
            <span style={{ width: 7, height: 7, borderRadius: 9999, background: "#16A34A" }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: "#15803D" }}>Zero hallucination</span>
          </div>

          <div
            style={{
              background: "#fff",
              border: "1px solid #E2E8F0",
              borderRadius: 18,
              boxShadow: "0 24px 60px rgba(15,23,42,0.12), 0 4px 12px rgba(15,23,42,0.05)",
              overflow: "hidden",
            }}
          >
            <div style={{ padding: "20px 22px", borderBottom: "1px solid #F1F5F9", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", color: "#94A3B8", fontWeight: 600, marginBottom: 5 }}>
                  Underwriting Summary
                </div>
                <div style={{ fontSize: 16, fontWeight: 600, color: "#0F172A" }}>Maple Court Apartments</div>
                <div style={{ fontSize: 12.5, color: "#64748B", marginTop: 2 }}>Garland, TX · 184 units · Class B</div>
              </div>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  padding: "4px 10px",
                  borderRadius: 9999,
                  fontSize: 11,
                  fontWeight: 600,
                  background: "rgba(22,163,74,0.10)",
                  color: "#15803D",
                  border: "1px solid rgba(22,163,74,0.20)",
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: 9999, background: "#16A34A" }} /> Complete
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "#F1F5F9" }}>
              <div style={{ background: "#fff", padding: "18px 22px" }}>
                <div style={{ fontSize: 11, color: "#94A3B8", fontWeight: 600, marginBottom: 7 }}>Pro Forma NOI</div>
                <div style={{ fontFamily: MONO, fontSize: 25, fontWeight: 600, color: "#0F172A", fontVariantNumeric: "tabular-nums", letterSpacing: "-0.01em" }}>
                  $2.34M
                </div>
                <div style={{ fontSize: 11.5, color: "#16A34A", fontWeight: 600, marginTop: 4 }}>▲ 12.4% vs. in place</div>
              </div>
              <div style={{ background: "#fff", padding: "18px 22px" }}>
                <div style={{ fontSize: 11, color: "#94A3B8", fontWeight: 600, marginBottom: 7 }}>Entry Cap Rate</div>
                <div style={{ fontFamily: MONO, fontSize: 25, fontWeight: 600, color: "#0F172A", fontVariantNumeric: "tabular-nums", letterSpacing: "-0.01em" }}>
                  5.48%
                </div>
                <div style={{ fontSize: 11.5, color: "#64748B", fontWeight: 500, marginTop: 4 }}>on $42.5M basis</div>
              </div>
            </div>

            <div style={{ padding: "18px 22px", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px 14px", borderTop: "1px solid #F1F5F9" }}>
              {summaryStats.map((s) => (
                <div key={s.label}>
                  <div style={{ fontSize: 10.5, color: "#94A3B8", fontWeight: 600, marginBottom: 5 }}>{s.label}</div>
                  <div style={{ fontFamily: MONO, fontSize: 17, fontWeight: 600, color: s.color, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
                </div>
              ))}
            </div>

            <div style={{ padding: "14px 22px", background: "#F8FAFC", borderTop: "1px solid #F1F5F9", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ fontSize: 11.5, color: "#64748B", fontWeight: 500 }}>312 line items · 4 source documents</div>
              <span style={{ fontSize: 11.5, color: "#F97316", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}>
                View audit trail →
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* TRUST STRIP */}
      <section
        style={{
          position: "relative",
          zIndex: 10,
          borderTop: "1px solid #E2E8F0",
          borderBottom: "1px solid #E2E8F0",
          background: "rgba(255,255,255,0.6)",
        }}
      >
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "22px 40px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.09em", color: "#94A3B8", fontWeight: 600 }}>
            Built for the acquisitions desk
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 34, flexWrap: "wrap" }}>
            {["Offering Memorandums", "T12 & P&L", "Rent Rolls", "PSAs", "Operating Statements"].map((label, i, arr) => (
              <span key={label} style={{ display: "flex", alignItems: "center", gap: 34 }}>
                <span style={{ fontSize: 14, color: "#64748B", fontWeight: 600 }}>{label}</span>
                {i < arr.length - 1 && <span style={{ width: 4, height: 4, borderRadius: 9999, background: "#CBD5E1" }} />}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" style={{ position: "relative", zIndex: 10, maxWidth: 1200, margin: "0 auto", padding: "96px 40px 40px" }}>
        <div style={{ maxWidth: 660, marginBottom: 52 }}>
          <div style={sectionEyebrow}>How it works</div>
          <h2 style={{ fontSize: 42, lineHeight: 1.1, letterSpacing: "-0.03em", fontWeight: 600, margin: "0 0 18px", color: "#0F172A" }}>
            From a messy deal room to a model you can{" "}
            <span style={{ fontFamily: SERIF_DISPLAY, fontStyle: "italic", fontWeight: 500 }}>defend</span>.
          </h2>
          <p style={{ fontSize: 17, lineHeight: 1.6, color: "#475569", margin: 0 }}>
            No templates to wrangle, no copying out of PDFs. Three steps from raw documents to a complete underwriting.
          </p>
        </div>

        <div className="uw-how" style={{ display: "grid", gridTemplateColumns: "1fr 46px 1fr 46px 1fr", alignItems: "stretch", gap: 0 }}>
          {/* STEP 1 */}
          <StepCard n="1" phase="Ingest" title="Drop the deal room" body="Any PDF, any format. Vision grade OCR reads every page and digitizes handwriting without inventing a single number.">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 13 }}>
              <span style={panelLabel}>Deal room</span>
              <span style={{ fontFamily: MONO, fontSize: 10, color: "#94A3B8" }}>4 files · 115p</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
              {dealFiles.map((f) => (
                <div key={f.name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={pdfChip}>PDF</div>
                  <span style={{ flex: 1, fontSize: 12.5, fontWeight: 600, color: "#0F172A" }}>{f.name}</span>
                  <span style={{ fontFamily: MONO, fontSize: 10.5, color: "#94A3B8" }}>{f.pages}</span>
                  <span style={checkDot}>✓</span>
                </div>
              ))}
            </div>
          </StepCard>

          <Connector />

          {/* STEP 2 */}
          <StepCard n="2" phase="Normalize" title="Normalize and reconcile" body="Every raw line maps to a standard category. Duplicates removed, taxes and fees recomputed, conflicting documents reconciled by priority.">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 13 }}>
              <span style={panelLabel}>Expense map</span>
              <span style={{ fontFamily: MONO, fontSize: 10, color: "#94A3B8" }}>312 lines</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
              {expenseMap.map((row) => (
                <div key={row.raw} style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <span
                    style={{
                      fontFamily: MONO,
                      fontSize: 10.5,
                      color: row.tone === "dropped" ? "#94A3B8" : "#475569",
                      background: "#fff",
                      border: "1px solid #E2E8F0",
                      borderRadius: 6,
                      padding: "4px 8px",
                      textDecoration: row.tone === "dropped" ? "line-through" : "none",
                    }}
                  >
                    {row.raw}
                  </span>
                  <span style={{ color: "#CBD5E1", fontSize: 12 }}>→</span>
                  <span
                    style={
                      row.tone === "dropped"
                        ? { fontSize: 11, fontWeight: 600, color: "#B91C1C", background: "rgba(220,38,38,0.08)", border: "1px solid rgba(220,38,38,0.20)", borderRadius: 6, padding: "4px 8px" }
                        : { fontSize: 11, fontWeight: 600, color: "#C2410C", background: "rgba(249,115,22,0.10)", border: "1px solid rgba(249,115,22,0.22)", borderRadius: 6, padding: "4px 8px" }
                    }
                  >
                    {row.to}
                  </span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: "auto", paddingTop: 13, display: "flex", alignItems: "center", gap: 8, borderTop: "1px solid #EEF2F6" }}>
              <span style={{ width: 6, height: 6, borderRadius: 9999, background: "#16A34A" }} />
              <span style={{ fontSize: 11, color: "#475569", fontWeight: 500 }}>Taxes recomputed at 1.2% of price</span>
            </div>
          </StepCard>

          <Connector />

          {/* STEP 3 */}
          <StepCard n="3" phase="Underwrite" title="Underwrite and export" body="A deterministic five step model returns NOI, cap rate and full returns. Stress the assumptions, then export in one click.">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 13 }}>
              <span style={panelLabel}>Output</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontFamily: MONO, fontSize: 10, color: "#15803D" }}>
                <span style={{ width: 5, height: 5, borderRadius: 9999, background: "#16A34A" }} />Complete
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 13 }}>
              {[
                { k: "NOI", v: "$2.34M", c: "#0F172A" },
                { k: "Cap", v: "5.48%", c: "#0F172A" },
                { k: "IRR", v: "18.2%", c: "#16A34A" },
              ].map((m) => (
                <div key={m.k} style={{ background: "#fff", border: "1px solid #E2E8F0", borderRadius: 9, padding: "9px 10px" }}>
                  <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.06em", color: "#94A3B8", fontWeight: 600, marginBottom: 4 }}>{m.k}</div>
                  <div style={{ fontFamily: MONO, fontSize: 14, fontWeight: 600, color: m.c }}>{m.v}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: "auto", display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
              {[
                { label: "Excel", dot: "#16A34A" },
                { label: "PDF", dot: "#DC2626" },
                { label: "Memo", dot: "#F97316" },
              ].map((e) => (
                <span key={e.label} style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "#fff", border: "1px solid #E2E8F0", borderRadius: 9999, padding: "5px 11px", fontSize: 11, fontWeight: 600, color: "#475569" }}>
                  <span style={{ width: 6, height: 6, borderRadius: 9999, background: e.dot }} />
                  {e.label}
                </span>
              ))}
            </div>
          </StepCard>
        </div>
      </section>

      {/* THE MODEL (DARK) */}
      <section id="model" style={{ position: "relative", zIndex: 10, marginTop: 84, background: "#0F172A", color: "#fff", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: -180, right: -120, width: 620, height: 620, borderRadius: "100%", background: "radial-gradient(circle, rgba(249,115,22,0.18) 0%, transparent 60%)", filter: "blur(60px)", pointerEvents: "none" }} />
        <div style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(to right, rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.025) 1px, transparent 1px)", backgroundSize: "34px 34px", pointerEvents: "none" }} />

        <div className="uw-model" style={{ position: "relative", maxWidth: 1200, margin: "0 auto", padding: "88px 40px", display: "grid", gridTemplateColumns: "0.92fr 1.08fr", gap: 64, alignItems: "center" }}>
          <div>
            <div style={sectionEyebrow}>The model</div>
            <h2 style={{ fontSize: 40, lineHeight: 1.12, letterSpacing: "-0.03em", fontWeight: 600, margin: "0 0 18px" }}>
              The math is <span style={{ fontFamily: SERIF_DISPLAY, fontStyle: "italic", fontWeight: 500, color: "#F97316" }}>deterministic</span>. The AI never touches it.
            </h2>
            <p style={{ fontSize: 16.5, lineHeight: 1.65, color: "#94A3B8", margin: "0 0 28px" }}>
              AI extracts and normalizes. Then a fixed, auditable engine runs the numbers the same way every time, with no black box on the figures that matter.
            </p>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 10, padding: "11px 16px", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 11, background: "rgba(255,255,255,0.04)" }}>
              <span style={{ fontSize: 13, color: "#CBD5E1", fontWeight: 500 }}>Includes the</span>
              <span style={{ fontFamily: MONO, fontSize: 13, color: "#fff", fontWeight: 600 }}>38%</span>
              <span style={{ fontSize: 13, color: "#CBD5E1", fontWeight: 500 }}>expense ratio floor &amp; reserve logic</span>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {modelSteps.map((step, i) => (
              <div
                key={step.n}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 18,
                  padding: "16px 20px",
                  border: "1px solid rgba(255,255,255,0.10)",
                  borderTop: i === 0 ? "1px solid rgba(255,255,255,0.10)" : "none",
                  borderRadius: i === 0 ? "14px 14px 0 0" : "0",
                  background: "rgba(255,255,255,0.03)",
                }}
              >
                <span style={{ fontFamily: MONO, fontSize: 12, color: "#F97316", fontWeight: 600, width: 22 }}>{step.n}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#fff" }}>{step.title}</div>
                  <div style={{ fontSize: 12.5, color: "#94A3B8", marginTop: 2 }}>{step.sub}</div>
                </div>
                <span style={{ fontFamily: MONO, fontSize: 14, color: step.valColor, fontWeight: 600 }}>{step.val}</span>
              </div>
            ))}
            {/* Step 05 — highlighted Returns */}
            <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "16px 20px", border: "1px solid rgba(249,115,22,0.45)", borderTop: "none", borderRadius: "0 0 14px 14px", background: "rgba(249,115,22,0.10)" }}>
              <span style={{ fontFamily: MONO, fontSize: 12, color: "#F97316", fontWeight: 600, width: 22 }}>05</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: "#fff" }}>Returns</div>
                <div style={{ fontSize: 12.5, color: "#CBD5E1", marginTop: 2 }}>5 year hold · IRR, MOIC, Cash on Cash</div>
              </div>
              <span style={{ fontFamily: MONO, fontSize: 16, color: "#FB923C", fontWeight: 600 }}>18.2% IRR</span>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" style={{ position: "relative", zIndex: 10, maxWidth: 1200, margin: "0 auto", padding: "96px 40px 40px" }}>
        <div style={{ maxWidth: 660, marginBottom: 52 }}>
          <div style={sectionEyebrow}>The platform</div>
          <h2 style={{ fontSize: 42, lineHeight: 1.1, letterSpacing: "-0.03em", fontWeight: 600, margin: "0 0 18px", color: "#0F172A" }}>
            Everything the analyst does by hand, only{" "}
            <span style={{ fontFamily: SERIF_DISPLAY, fontStyle: "italic", fontWeight: 500 }}>traceable</span>.
          </h2>
        </div>

        <div className="uw-features" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 22 }}>
          {features.map((f) => (
            <div key={f.title} style={{ background: "#fff", border: "1px solid #E2E8F0", borderRadius: 16, padding: 26, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
              <div style={{ width: 38, height: 38, borderRadius: 10, background: "rgba(249,115,22,0.10)", border: "1px solid rgba(249,115,22,0.20)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 18 }}>
                {f.icon}
              </div>
              <h3 style={{ fontSize: 16.5, fontWeight: 600, margin: "0 0 9px", color: "#0F172A" }}>{f.title}</h3>
              <p style={{ fontSize: 14, lineHeight: 1.6, color: "#475569", margin: 0 }}>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* SECURITY */}
      <section id="security" style={{ position: "relative", zIndex: 10, maxWidth: 1200, margin: "0 auto", padding: "96px 40px 40px" }}>
        <div className="uw-security" style={{ background: "#fff", border: "1px solid #E2E8F0", borderRadius: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.05)", overflow: "hidden", display: "grid", gridTemplateColumns: "1fr 1fr" }}>
          <div style={{ padding: 48 }}>
            <div style={sectionEyebrow}>Trust &amp; security</div>
            <h2 style={{ fontSize: 32, lineHeight: 1.15, letterSpacing: "-0.025em", fontWeight: 600, margin: "0 0 16px", color: "#0F172A" }}>
              A number you can put in front of the investment committee.
            </h2>
            <p style={{ fontSize: 15.5, lineHeight: 1.65, color: "#475569", margin: "0 0 26px" }}>
              Confidential deal data stays isolated per engagement. Nothing about the model is a guess you can&apos;t inspect, and every output points back to the document that produced it.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {[
                "Source traced figures with page level citations",
                "Isolated, encrypted document storage per deal",
                "Immutable audit log of every transformation",
              ].map((t) => (
                <div key={t} style={{ display: "flex", alignItems: "center", gap: 11 }}>
                  <div style={{ width: 6, height: 6, borderRadius: 9999, background: "#16A34A" }} />
                  <span style={{ fontSize: 14.5, color: "#0F172A", fontWeight: 500 }}>{t}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ background: "#F8FAFC", borderLeft: "1px solid #E2E8F0", padding: 48, display: "flex", flexDirection: "column", justifyContent: "center", gap: 18 }}>
            {[
              { n: "312", t: "line items, each linked to a source page" },
              { n: "0", t: "figures fabricated by the model" },
              { n: "100%", t: "of the math reproducible, line by line" },
            ].map((row, i, arr) => (
              <div key={row.n}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
                  <span style={{ fontFamily: MONO, fontSize: 38, fontWeight: 600, color: "#0F172A", fontVariantNumeric: "tabular-nums" }}>{row.n}</span>
                  <span style={{ fontSize: 14, color: "#64748B", fontWeight: 500 }}>{row.t}</span>
                </div>
                {i < arr.length - 1 && <div style={{ height: 1, background: "#E2E8F0", marginTop: 18 }} />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section id="cta" style={{ position: "relative", zIndex: 10, maxWidth: 1200, margin: "96px auto 0", padding: "0 40px" }}>
        <div style={{ position: "relative", background: "#0F172A", borderRadius: 24, padding: "72px 56px", overflow: "hidden", textAlign: "center" }}>
          <div style={{ position: "absolute", top: -160, left: "50%", transform: "translateX(-50%)", width: 760, height: 480, borderRadius: "100%", background: "radial-gradient(circle, rgba(249,115,22,0.22) 0%, transparent 62%)", filter: "blur(60px)", pointerEvents: "none" }} />
          <div style={{ position: "relative" }}>
            <h2 style={{ fontSize: 44, lineHeight: 1.1, letterSpacing: "-0.03em", fontWeight: 600, margin: "0 0 18px", color: "#fff" }}>
              Bring your next deal. <span style={{ fontFamily: SERIF_DISPLAY, fontStyle: "italic", fontWeight: 500, color: "#FB923C" }}>Underwrite it today.</span>
            </h2>
            <p style={{ fontSize: 17, lineHeight: 1.6, color: "#94A3B8", margin: "0 auto 34px", maxWidth: 520 }}>
              Request access and run your first underwriting on a live document set this week.
            </p>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, flexWrap: "wrap" }}>
              <Link href="/signup" style={{ fontSize: 15, color: "#fff", textDecoration: "none", fontWeight: 600, background: "#F97316", padding: "14px 28px", borderRadius: 11, boxShadow: "0 6px 22px rgba(249,115,22,0.45)" }}>
                Request access
              </Link>
              <Link href="/signin" style={{ fontSize: 15, color: "#fff", textDecoration: "none", fontWeight: 600, padding: "14px 24px", borderRadius: 11, border: "1px solid rgba(255,255,255,0.2)", background: "rgba(255,255,255,0.04)" }}>
                Book a walkthrough
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{ position: "relative", zIndex: 10, marginTop: 88, background: "#0F172A", overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(to right, rgba(255,255,255,0.022) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.022) 1px, transparent 1px)", backgroundSize: "34px 34px", pointerEvents: "none" }} />

        <div className="uw-footer" style={{ position: "relative", maxWidth: 1200, margin: "0 auto", padding: "72px 40px 0", display: "grid", gridTemplateColumns: "1.6fr 1fr 1fr 1fr", gap: 48 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 18 }}>
              <BrandSquare />
              <span style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.02em", color: "#fff" }}>Underwrite</span>
              <span style={{ fontFamily: SERIF_READER, fontStyle: "italic", fontSize: 14, color: "#FB923C", marginLeft: -3 }}>AI</span>
            </div>
            <p style={{ fontSize: 14, lineHeight: 1.65, color: "#94A3B8", margin: "0 0 22px", maxWidth: 290 }}>
              From deal room to defensible underwriting. Read every page, normalize the expenses, and produce an institutional model with every figure traced to source.
            </p>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "7px 13px", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 9999, background: "rgba(255,255,255,0.03)", whiteSpace: "nowrap" }}>
              <span style={{ position: "relative", display: "flex", height: 7, width: 7 }}>
                <span style={{ position: "absolute", display: "inline-flex", height: "100%", width: "100%", borderRadius: 9999, background: "#16A34A", opacity: 0.75, animation: "uw_ping 1.8s cubic-bezier(0,0,0.2,1) infinite" }} />
                <span style={{ position: "relative", display: "inline-flex", borderRadius: 9999, height: 7, width: 7, background: "#22C55E" }} />
              </span>
              <span style={{ fontSize: 12, color: "#CBD5E1", fontWeight: 500 }}>All systems operational</span>
            </div>
          </div>

          <FooterColumn title="Product" links={[
            { label: "How it works", href: "#how" },
            { label: "The model", href: "#model" },
            { label: "Platform", href: "#features" },
            { label: "Security", href: "#security" },
            { label: "Pricing", href: "#" },
          ]} />
          <FooterColumn title="Company" links={[
            { label: "About", href: "#" },
            { label: "Customers", href: "#" },
            { label: "Careers", href: "#" },
            { label: "Contact", href: "#" },
          ]} />
          <FooterColumn title="Resources" links={[
            { label: "Documentation", href: "#" },
            { label: "Security overview", href: "#security" },
            { label: "Changelog", href: "#" },
            { label: "System status", href: "#" },
          ]} />
        </div>

        <div style={{ position: "relative", maxWidth: 1200, margin: "56px auto 0", padding: "24px 40px 36px", borderTop: "1px solid rgba(255,255,255,0.08)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <span style={{ fontSize: 13, color: "#64748B" }}>© 2026 Underwrite AI. All rights reserved.</span>
          <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
            <a href="#" className="uw-foot-link" style={{ ...footerLink, fontSize: 13 }}>Privacy Policy</a>
            <a href="#" className="uw-foot-link" style={{ ...footerLink, fontSize: 13 }}>Terms of Service</a>
            <a href="#" className="uw-foot-link" style={{ ...footerLink, fontSize: 13 }}>Security</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ---------- small building blocks ---------- */

const panelLabel: CSSProperties = {
  fontFamily: MONO,
  fontSize: 9.5,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#94A3B8",
  fontWeight: 600,
};

const pdfChip: CSSProperties = {
  width: 32,
  height: 22,
  borderRadius: 5,
  background: "rgba(249,115,22,0.10)",
  border: "1px solid rgba(249,115,22,0.22)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: MONO,
  fontSize: 8.5,
  fontWeight: 700,
  color: "#C2410C",
};

const checkDot: CSSProperties = {
  width: 15,
  height: 15,
  borderRadius: 9999,
  background: "rgba(22,163,74,0.12)",
  color: "#16A34A",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 9,
  fontWeight: 700,
};

function BrandSquare() {
  return (
    <div style={{ width: 30, height: 30, borderRadius: 8, background: "#F97316", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 4px 14px rgba(249,115,22,0.35)" }}>
      <div style={{ width: 12, height: 12, border: "2.5px solid #fff", borderRadius: 3, transform: "rotate(45deg)" }} />
    </div>
  );
}

function BrandMark() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
      <BrandSquare />
      <span style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em", color: "#0F172A" }}>Underwrite</span>
      <span style={{ fontFamily: SERIF_READER, fontStyle: "italic", fontSize: 14, color: "#F97316", fontWeight: 400, marginLeft: -3 }}>AI</span>
    </div>
  );
}

function PingDot() {
  return (
    <span style={{ position: "relative", display: "flex", height: 8, width: 8 }}>
      <span style={{ position: "absolute", display: "inline-flex", height: "100%", width: "100%", borderRadius: 9999, background: "#F97316", opacity: 0.75, animation: "uw_ping 1.6s cubic-bezier(0,0,0.2,1) infinite" }} />
      <span style={{ position: "relative", display: "inline-flex", borderRadius: 9999, height: 8, width: 8, background: "#F97316" }} />
    </span>
  );
}

function HeroStat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div style={{ fontFamily: MONO, fontSize: 22, fontWeight: 600, color: "#0F172A", fontVariantNumeric: "tabular-nums" }}>{value}</div>
      <div style={{ fontSize: 12.5, color: "#94A3B8", fontWeight: 500, marginTop: 2 }}>{label}</div>
    </div>
  );
}

function Connector() {
  return (
    <div className="uw-connector" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 30, height: 30, borderRadius: 9999, background: "#fff", border: "1px solid #E2E8F0", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", display: "flex", alignItems: "center", justifyContent: "center", color: "#F97316", fontSize: 14, fontWeight: 700 }}>→</div>
    </div>
  );
}

function StepCard({ n, phase, title, body, children }: { n: string; phase: string; title: string; body: string; children: ReactNode }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #E2E8F0", borderRadius: 18, padding: 26, boxShadow: "0 1px 3px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <div style={{ width: 32, height: 32, borderRadius: 9999, background: "#F97316", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: MONO, fontSize: 14, fontWeight: 600, boxShadow: "0 4px 12px rgba(249,115,22,0.35)" }}>{n}</div>
        <span style={{ fontFamily: MONO, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: "#94A3B8", fontWeight: 600 }}>{phase}</span>
      </div>
      <h3 style={{ fontSize: 19, fontWeight: 600, margin: "0 0 9px", color: "#0F172A", letterSpacing: "-0.01em" }}>{title}</h3>
      <p style={{ fontSize: 14, lineHeight: 1.6, color: "#475569", margin: 0 }}>{body}</p>
      <div style={{ marginTop: 22, background: "#F8FAFC", border: "1px solid #EEF2F6", borderRadius: 14, padding: 15, flex: 1, display: "flex", flexDirection: "column" }}>
        {children}
      </div>
    </div>
  );
}

function FooterColumn({ title, links }: { title: string; links: { label: string; href: string }[] }) {
  return (
    <div>
      <div style={{ fontFamily: MONO, fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "#64748B", fontWeight: 600, marginBottom: 18 }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
        {links.map((l) => (
          <a key={l.label} href={l.href} className="uw-foot-link" style={footerLink}>{l.label}</a>
        ))}
      </div>
    </div>
  );
}
