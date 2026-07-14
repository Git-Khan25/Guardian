import React, { useState } from "react";

function isValidUrl(value) {
  try {
    const u = new URL(value.startsWith("http") ? value : `https://${value}`);
    return Boolean(u.hostname && u.hostname.includes("."));
  } catch {
    return false;
  }
}

export default function ScanInput({ onScan, disabled }) {
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);

  const valid = isValidUrl(value.trim());

  const submit = () => {
    setTouched(true);
    if (!valid || disabled) return;
    const normalized = value.trim().startsWith("http") ? value.trim() : `https://${value.trim()}`;
    onScan(normalized);
  };

  return (
    <div className="paper-card rounded-sm p-5">
      <label className="block font-mono text-[11px] uppercase tracking-widest text-paper/40 mb-2">
        Live scan &mdash; site under review
      </label>
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          onBlur={() => setTouched(true)}
          placeholder="example.com"
          disabled={disabled}
          className="flex-1 bg-ink-900 border border-ink-600 rounded-sm px-4 py-3 text-paper placeholder:text-paper/25 font-mono text-sm focus:outline-none focus:border-amber-accent/60 disabled:opacity-40"
        />
        <button
          onClick={submit}
          disabled={disabled || !value}
          className="stamp shrink-0 px-6 py-3 rounded-sm border-amber-accent text-amber-accent hover:bg-amber-accent hover:text-ink-950 transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-amber-accent text-xs"
        >
          Open case
        </button>
      </div>
      {touched && value && !valid && (
        <p className="mt-2 text-xs text-verdict-contradicted font-mono">
          Enter a reachable URL, e.g. example.com
        </p>
      )}
      <p className="mt-3 text-xs text-paper/35">
        Runs the full pipeline live: fetches the policy, extracts claims, captures traffic,
        classifies domains, and grounds a verdict in the evidence. Typically 20–60s; capped at
        90s. Scanning the same site again is instant — results are cached for 24 hours. Very
        large or bot-protected sites (social apps, login walls) may not complete.
      </p>
    </div>
  );
}
