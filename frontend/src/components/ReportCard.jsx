import React, { useState } from "react";
import TrustScoreBadge from "./TrustScoreBadge.jsx";

const VERDICT_STYLES = {
  confirmed: {
    label: "Confirmed",
    text: "text-verdict-confirmed",
    border: "border-verdict-confirmed/40",
    dot: "bg-verdict-confirmed",
  },
  contradicted: {
    label: "Contradicted",
    text: "text-verdict-contradicted",
    border: "border-verdict-contradicted/40",
    dot: "bg-verdict-contradicted",
  },
  unverifiable: {
    label: "Unverifiable",
    text: "text-verdict-unverifiable",
    border: "border-verdict-unverifiable/40",
    dot: "bg-verdict-unverifiable",
  },
};

function SourceTag({ source }) {
  const label = source === "model" ? "extended check" : source === "blocklist" ? "blocklist" : "unresolved";
  const highlight = source === "model";
  return (
    <span
      className={`inline-block font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ${
        highlight
          ? "border-amber-accent/60 text-amber-accent bg-amber-accent/10"
          : "border-paper/15 text-paper/40"
      }`}
    >
      {label}
    </span>
  );
}

function ClaimCard({ entry, classifiedByDomain }) {
  const [open, setOpen] = useState(false);
  const style = VERDICT_STYLES[entry.verdict] || VERDICT_STYLES.unverifiable;

  return (
    <div className={`paper-card rounded-sm border ${style.border} overflow-hidden`}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left p-4 flex items-start gap-3"
      >
        <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${style.dot}`} />
        <div className="flex-1 min-w-0">
          <div
            className={`stamp inline-block text-[10px] px-2 py-0.5 rounded-sm mb-2 ${style.text} ${style.border}`}
          >
            {style.label}
          </div>
          <p className="font-display text-[15px] leading-snug text-paper">{entry.claim}</p>
        </div>
        <span className="font-mono text-paper/30 text-xs mt-1">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-paper/10 pt-3">
          <p className="text-sm text-paper/60 mb-3 leading-relaxed">{entry.explanation}</p>
          {entry.evidence && entry.evidence.length > 0 ? (
            <div className="space-y-1.5">
              <div className="font-mono text-[10px] uppercase tracking-widest text-paper/35 mb-1">
                Evidence
              </div>
              {entry.evidence.map((ev, i) => {
                const domainMatch = Object.keys(classifiedByDomain || {}).find((d) =>
                  ev.includes(d)
                );
                const source = domainMatch ? classifiedByDomain[domainMatch].source : null;
                return (
                  <div
                    key={i}
                    className="flex items-center justify-between gap-2 bg-ink-900 rounded-sm px-2.5 py-1.5"
                  >
                    <span className="font-mono text-xs text-paper/70 truncate">{ev}</span>
                    {source && <SourceTag source={source} />}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="font-mono text-xs text-paper/30 italic">
              No domain evidence bears on this claim.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function ReportCard({ report, onScanAnother, onRescanFresh }) {
  const verdicts = report.verdicts || [];
  const hero = verdicts.find((v) => v.verdict === "contradicted");
  const classifiedByDomain = {};
  (report.classified_domains || []).forEach((d) => {
    classifiedByDomain[d.domain] = d;
  });

  const modelClassified = (report.classified_domains || []).filter((d) => d.source === "model");
  const isDemo = String(report.scan_id || "").startsWith("demo-");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-widest text-paper/40 mb-1">
            Case file
          </div>
          <h2 className="font-display text-3xl text-paper">{report.site_name || report.url}</h2>
        </div>
        <div className="flex items-center gap-3">
          {!isDemo && onRescanFresh && (
            <button
              onClick={onRescanFresh}
              className="font-mono text-xs uppercase tracking-widest text-paper/50 hover:text-amber-accent border border-paper/15 hover:border-amber-accent/50 rounded-sm px-4 py-2 transition-colors"
            >
              Rescan fresh
            </button>
          )}
          <button
            onClick={onScanAnother}
            className="font-mono text-xs uppercase tracking-widest text-paper/50 hover:text-amber-accent border border-paper/15 hover:border-amber-accent/50 rounded-sm px-4 py-2 transition-colors"
          >
            Scan another
          </button>
        </div>
      </div>

      <TrustScoreBadge score={report.trust_score} siteName={report.site_name || report.url} />

      {hero && (
        <div className="border-2 border-verdict-contradicted/50 rounded-sm p-5 bg-verdict-contradicted/[0.06]">
          <div className="stamp inline-block text-[11px] px-3 py-1 rounded-sm text-verdict-contradicted border-verdict-contradicted mb-3">
            Headline contradiction
          </div>
          <p className="font-display text-xl text-paper leading-snug mb-2">{hero.claim}</p>
          <p className="text-sm text-paper/60">{hero.explanation}</p>
        </div>
      )}

      {modelClassified.length > 0 && (
        <div className="font-mono text-xs text-paper/45 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-accent" />
          {modelClassified.length} domain{modelClassified.length > 1 ? "s" : ""} classified beyond
          the static blocklist through an extended pattern check.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {verdicts.map((v, i) => (
          <ClaimCard key={i} entry={v} classifiedByDomain={classifiedByDomain} />
        ))}
      </div>

      {report.errors && report.errors.length > 0 && (
        <div className="paper-card rounded-sm p-4 border border-paper/10">
          <div className="font-mono text-[11px] uppercase tracking-widest text-paper/35 mb-2">
            Pipeline notes (degraded, non-fatal)
          </div>
          {report.errors.map((e, i) => (
            <div key={i} className="text-xs text-paper/45 font-mono">
              [{e.stage}] {e.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
