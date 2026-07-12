import React, { useEffect, useRef, useState } from "react";
import ScanInput from "./components/ScanInput.jsx";
import PresetAppPicker from "./components/PresetAppPicker.jsx";
import PipelineProgress from "./components/PipelineProgress.jsx";
import ReportCard from "./components/ReportCard.jsx";
import { api } from "./api/client.js";

const DEMO_STAGE_SEQUENCE = [
  "fetching_policy",
  "extracting_claims",
  "capturing_traffic",
  "classifying_domains",
  "generating_verdict",
  "complete",
];

export default function App() {
  const [view, setView] = useState("home"); // home | progress | report
  const [stage, setStage] = useState("fetching_policy");
  const [siteLabel, setSiteLabel] = useState("");
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const pollRef = useRef(null);
  const demoTimerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (demoTimerRef.current) clearInterval(demoTimerRef.current);
    };
  }, []);

  const reset = () => {
    setView("home");
    setReport(null);
    setError(null);
    setBusy(false);
    setStage("fetching_policy");
    if (pollRef.current) clearInterval(pollRef.current);
    if (demoTimerRef.current) clearInterval(demoTimerRef.current);
  };

  const runDemo = async (appId) => {
    setError(null);
    setBusy(true);
    setSiteLabel(appId);
    setView("progress");
    setStage("fetching_policy");

    // Data is already cached — but we still walk the same 5-stage UI path a
    // live scan would take, briefly animated, so judges see the real pipeline shape.
    let i = 0;
    demoTimerRef.current = setInterval(() => {
      i += 1;
      setStage(DEMO_STAGE_SEQUENCE[i] || "complete");
      if (i >= DEMO_STAGE_SEQUENCE.length - 1) {
        clearInterval(demoTimerRef.current);
      }
    }, 260);

    try {
      const data = await api.getDemo(appId);
      setTimeout(() => {
        setReport(data);
        setView("report");
        setBusy(false);
      }, 1500);
    } catch (e) {
      clearInterval(demoTimerRef.current);
      setError(String(e.message || e));
      setBusy(false);
      setView("home");
    }
  };

  const runLiveScan = async (url) => {
    setError(null);
    setBusy(true);
    setSiteLabel(url);
    setView("progress");
    setStage("fetching_policy");

    try {
      const { scan_id } = await api.startScan(url);
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.getStatus(scan_id);
          setStage(status.pipeline_stage);
          if (status.complete) {
            clearInterval(pollRef.current);
            const full = await api.getReport(scan_id);
            setReport(full);
            setView("report");
            setBusy(false);
          }
        } catch (e) {
          clearInterval(pollRef.current);
          setError(String(e.message || e));
          setBusy(false);
          setView("home");
        }
      }, 1500);
    } catch (e) {
      setError(String(e.message || e));
      setBusy(false);
      setView("home");
    }
  };

  return (
    <div className="min-h-screen">
      <header className="border-b border-paper/10">
        <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-sm border-2 border-amber-accent flex items-center justify-center font-display text-amber-accent text-sm">
              CG
            </div>
            <div>
              <div className="font-display text-lg text-paper leading-none">Contract Guardian</div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-paper/35">
                verify the promise, not the prose
              </div>
            </div>
          </div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-paper/30">
            evidence-backed privacy verification
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        {view === "home" && (
          <div className="space-y-10">
            <div className="max-w-2xl">
              <h1 className="font-display text-4xl sm:text-5xl text-paper leading-[1.1] mb-4">
                Every privacy policy makes promises.
                <br />
                <span className="text-amber-accent">We check them against the wire.</span>
              </h1>
              <p className="text-paper/55 leading-relaxed">
                Contract Guardian extracts the concrete, checkable claims from a site's privacy
                policy, watches its real network traffic, and shows you exactly where the two
                agree — or don't. Domain-level evidence only; we never inspect encrypted payload
                contents.
              </p>
            </div>

            {error && (
              <div className="border border-verdict-contradicted/40 bg-verdict-contradicted/[0.08] rounded-sm px-4 py-3 font-mono text-xs text-verdict-contradicted">
                {error}
              </div>
            )}

            <section>
              <div className="font-mono text-[11px] uppercase tracking-widest text-paper/40 mb-3">
                Pre-scanned exhibits &mdash; instant
              </div>
              <PresetAppPicker onPick={runDemo} disabled={busy} />
            </section>

            <section>
              <ScanInput onScan={runLiveScan} disabled={busy} />
            </section>
          </div>
        )}

        {view === "progress" && (
          <div className="max-w-md mx-auto py-10">
            <PipelineProgress currentStage={stage} siteLabel={siteLabel} />
          </div>
        )}

        {view === "report" && report && (
          <ReportCard report={report} onScanAnother={reset} />
        )}
      </main>

      <footer className="max-w-5xl mx-auto px-6 py-10 text-center">
        <p className="font-mono text-[10px] uppercase tracking-widest text-paper/25">
          Domain-level traffic capture only &middot; no payload inspection &middot; demo tool, no
          accounts or persistent storage
        </p>
      </footer>
    </div>
  );
}
