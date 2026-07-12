import React from "react";

const STAGES = [
  { key: "fetching_policy", label: "Fetch policy", note: "locating privacy policy text" },
  { key: "extracting_claims", label: "Extract claims", note: "schema-constrained promises" },
  { key: "capturing_traffic", label: "Capture traffic", note: "domain-level, ~10s idle" },
  { key: "classifying_domains", label: "Classify domains", note: "blocklist + extended check" },
  { key: "generating_verdict", label: "Generate verdict", note: "grounded in evidence" },
];

export default function PipelineProgress({ currentStage, siteLabel }) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);
  const isComplete = currentStage === "complete";

  return (
    <div className="paper-card rounded-sm p-6">
      <div className="flex items-center justify-between mb-6">
        <span className="font-mono text-[11px] uppercase tracking-widest text-paper/40">
          Case in progress
        </span>
        <span className="font-mono text-[11px] text-amber-accent/80 truncate max-w-[50%]">
          {siteLabel}
        </span>
      </div>

      <div className="space-y-0">
        {STAGES.map((stage, i) => {
          const active = i === currentIndex && !isComplete;
          const done = isComplete || i < currentIndex;
          return (
            <div key={stage.key} className="flex items-start gap-4">
              <div className="flex flex-col items-center">
                <div
                  className={`w-3 h-3 rounded-full border-2 shrink-0 mt-1 ${
                    done
                      ? "bg-amber-accent border-amber-accent"
                      : active
                      ? "border-amber-accent pulse-dot"
                      : "border-paper/20"
                  }`}
                />
                {i < STAGES.length - 1 && (
                  <div
                    className={`w-px flex-1 min-h-[28px] ${
                      done ? "bg-amber-accent/50" : "bg-paper/10"
                    }`}
                  />
                )}
              </div>
              <div className="pb-6">
                <div
                  className={`font-display text-base ${
                    done || active ? "text-paper" : "text-paper/35"
                  }`}
                >
                  {stage.label}
                </div>
                <div className="text-xs text-paper/40 font-mono">{stage.note}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
