import React from "react";

const PRESETS = [
  { id: "shopnest", label: "ShopNest", tag: "e-commerce", blurb: "checkout & cart" },
  { id: "chatly", label: "Chatly", tag: "messaging", blurb: "chat & social" },
  { id: "fittrack", label: "FitTrack", tag: "health & fitness", blurb: "GPS & biometrics" },
];

export default function PresetAppPicker({ onPick, disabled }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {PRESETS.map((p) => (
        <button
          key={p.id}
          disabled={disabled}
          onClick={() => onPick(p.id)}
          className="group text-left paper-card rounded-sm p-4 transition-colors hover:border-amber-accent/50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-[11px] uppercase tracking-widest text-paper/40">
              exhibit
            </span>
            <span className="font-mono text-[11px] uppercase tracking-widest text-amber-accent/70">
              pre-scanned
            </span>
          </div>
          <div className="font-display text-xl text-paper mb-1 group-hover:text-amber-accent transition-colors">
            {p.label}
          </div>
          <div className="text-sm text-paper/50">
            {p.tag} &middot; {p.blurb}
          </div>
        </button>
      ))}
    </div>
  );
}
