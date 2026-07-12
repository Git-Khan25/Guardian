import React from "react";

export default function TrustScoreBadge({ score, siteName }) {
  const { confirmed = 0, contradicted = 0, unverifiable = 0 } = score || {};
  const total = confirmed + contradicted + unverifiable || 1;

  return (
    <div className="paper-card rounded-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-mono text-[11px] uppercase tracking-widest text-paper/40">
          Trust Score
        </span>
        <span className="font-mono text-[11px] text-paper/40">{siteName}</span>
      </div>

      <div className="flex h-2.5 rounded-full overflow-hidden mb-4 bg-ink-900">
        <div
          className="bg-verdict-confirmed"
          style={{ width: `${(confirmed / total) * 100}%` }}
        />
        <div
          className="bg-verdict-contradicted"
          style={{ width: `${(contradicted / total) * 100}%` }}
        />
        <div
          className="bg-verdict-unverifiable"
          style={{ width: `${(unverifiable / total) * 100}%` }}
        />
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-2 font-mono text-sm">
        <span className="text-verdict-confirmed">{confirmed} Confirmed</span>
        <span className="text-verdict-contradicted">{contradicted} Contradicted</span>
        <span className="text-verdict-unverifiable">{unverifiable} Unverifiable</span>
      </div>
    </div>
  );
}
