"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { InputForm } from "./InputForm";
import { Notice } from "./Notice";
import { ApprovedInputsPanel, ProvenancePanel } from "./ProvenancePanel";
import { ResultPanel } from "./ResultPanel";
import { ResultSkeleton } from "./ResultSkeleton";
import { TemperaturePanel } from "./TemperaturePanel";
import { WarningsPanel } from "./WarningsPanel";
import { WellDetail } from "./WellDetail";
import { WellSelector } from "./WellSelector";
import {
  API_BASE_URL,
  ApiClientError,
  USING_DEV_FALLBACK_URL,
  compareTemperatureMethods,
  getRequiredInputs,
  getWell,
  listScenarios,
  listWells,
  screenWell,
} from "@/lib/api";
import type {
  RequiredInputs,
  ScenarioSummary,
  ScreenResult,
  TemperatureComparison,
  UserInputValues,
  WellDetail as WellDetailType,
  WellSummary,
} from "@/lib/types";
import { isApproved } from "@/lib/types";

const DEFAULT_SCENARIO = "literature-screening-v1";

function messageFor(error: unknown): string {
  if (error instanceof ApiClientError) return error.message;
  return "Something went wrong while talking to the screening backend.";
}

/**
 * Orchestrates the workflow: pick a well, read its source data, supply the
 * inputs the backend will not invent, screen, then read the provenance.
 *
 * Which inputs are collected is decided by the API's required-inputs list for
 * the selected scenario: area_m2, z_top, z_base on the approved model; area_m2
 * and thickness_m on a NOT_VALIDATED legacy scenario. The workspace collects
 * them, calls the API and renders what comes back; it derives nothing.
 *
 * State is deliberately flat. A previous result is cleared the moment the
 * selected well changes, so a number can never be read against the wrong well.
 */
export function ScreeningWorkspace() {
  const [wells, setWells] = useState<WellSummary[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [scenario, setScenario] = useState(DEFAULT_SCENARIO);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WellDetailType | null>(null);
  const [inputs, setInputs] = useState<RequiredInputs | null>(null);
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [comparison, setComparison] = useState<TemperatureComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Bumped whenever the well or scenario changes. A response is applied only
  // if the generation it started under is still current, so a slow reply for
  // a previous selection can never land beside the new one.
  const generation = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [wellList, scenarioList] = await Promise.all([listWells(), listScenarios()]);
        if (cancelled) return;
        setWells(wellList);
        setScenarios(scenarioList);
        const preferred = scenarioList.find((s) => s.name === DEFAULT_SCENARIO);
        if (preferred) setScenario(preferred.name);
        else if (scenarioList.length > 0) setScenario(scenarioList[0].name);
      } catch (err) {
        if (!cancelled) setError(messageFor(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectWell = useCallback(
    async (wellId: string) => {
      const gen = ++generation.current;
      setSelectedId(wellId);
      // A stale result beside a new well would be worse than no result.
      setResult(null);
      setComparison(null);
      setError(null);
      setDetail(null);
      setInputs(null);
      try {
        const [wellDetail, requiredInputs] = await Promise.all([
          getWell(wellId),
          getRequiredInputs(wellId, scenario),
        ]);
        if (gen !== generation.current) return;
        setDetail(wellDetail);
        setInputs(requiredInputs);
      } catch (err) {
        if (gen === generation.current) setError(messageFor(err));
      }
    },
    [scenario],
  );

  // Required inputs and blockers depend on the scenario, and so does any
  // result already on screen: re-fetch the one and drop the others.
  async function changeScenario(next: string) {
    const gen = ++generation.current;
    setScenario(next);
    setResult(null);
    setComparison(null);
    setError(null);
    if (!selectedId) return;
    setInputs(null);
    try {
      const requiredInputs = await getRequiredInputs(selectedId, next);
      if (gen === generation.current) setInputs(requiredInputs);
    } catch (err) {
      if (gen === generation.current) setError(messageFor(err));
    }
  }

  // A scenario is legacy when the API says so; until the required inputs have
  // loaded, fall back to the scenario list's own validation status.
  const activeScenario = scenarios.find(
    (s) => s.name === scenario || s.aliases.includes(scenario),
  );
  const isLegacy = inputs
    ? inputs.model_path === "LEGACY_NOT_VALIDATED"
    : activeScenario?.validation_status === "NOT_VALIDATED";

  async function runScreening(values: UserInputValues) {
    if (!selectedId) return;
    const gen = generation.current;
    setBusy(true);
    setError(null);
    setComparison(null);
    // Drop the previous number before the request starts, not after it lands.
    setResult(null);
    try {
      const screened = await screenWell(selectedId, values, scenario);
      if (gen === generation.current) setResult(screened);
    } catch (err) {
      if (gen === generation.current) {
        setResult(null);
        setError(messageFor(err));
      }
    } finally {
      setBusy(false);
    }
  }

  async function runTemperatureComparison(values: UserInputValues) {
    if (!selectedId) return;
    const gen = generation.current;
    setBusy(true);
    setError(null);
    try {
      const compared = await compareTemperatureMethods(selectedId, values, scenario);
      if (gen === generation.current) setComparison(compared);
    } catch (err) {
      if (gen === generation.current) {
        setComparison(null);
        setError(messageFor(err));
      }
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <p className="unavailable" role="status">
        Loading wells from the screening backend...
      </p>
    );
  }

  if (wells.length === 0) {
    return (
      <Notice tone="stop" title="No wells available">
        <p>{error ?? "The backend returned no wells."}</p>
      </Notice>
    );
  }

  return (
    <>
      {USING_DEV_FALLBACK_URL ? (
        <div style={{ marginBottom: 16 }}>
          <Notice tone="stop" title="Backend URL not configured">
            <p>
              This build has no NEXT_PUBLIC_CCS_API_URL and is calling{" "}
              {API_BASE_URL}. Set it at build time and rebuild.
            </p>
          </Notice>
        </div>
      ) : null}

      {error ? (
        <div style={{ marginBottom: 16 }}>
          <Notice tone="stop" title="Request failed">
            <p>{error}</p>
          </Notice>
        </div>
      ) : null}

      <div className="grid">
        <div className="stack">
          <WellSelector wells={wells} selectedId={selectedId} onSelect={selectWell} />
          {detail ? <WellDetail detail={detail} inputs={inputs} /> : null}
          {selectedId ? (
            <InputForm
              scenarios={scenarios}
              scenario={scenario}
              required={inputs ? inputs.required : null}
              onScenarioChange={changeScenario}
              onSubmit={runScreening}
              onCompareTemperature={isLegacy ? runTemperatureComparison : null}
              busy={busy}
              disabled={!selectedId}
            />
          ) : null}
        </div>

        <div className="stack" aria-busy={busy} aria-live="polite">
          {!selectedId ? (
            <section className="panel">
              <h2>Getting started</h2>
              <p className="bucket-desc">
                Select a well, then supply the inputs the selected scenario
                requires. The approved model needs a storage area and the
                storage-assessment interval (z_top, z_base); a NOT_VALIDATED
                legacy scenario needs a storage area and a net reservoir
                thickness. None has a default: the source data does not contain
                them and no literature range covers them, so this tool will not
                invent any of them.
              </p>
            </section>
          ) : null}

          {busy ? <ResultSkeleton /> : null}
          {!busy && result ? <ResultPanel result={result} /> : null}
          {!busy && result ? (
            <WarningsPanel interpretation={result.interpretation} />
          ) : null}
          {!busy && comparison ? <TemperaturePanel comparison={comparison} /> : null}
          {!busy && result && !isApproved(result) && result.status === "screened" ? (
            <ProvenancePanel result={result} />
          ) : null}
          {!busy && result && isApproved(result) && result.status === "evaluated" ? (
            <ApprovedInputsPanel result={result} />
          ) : null}
        </div>
      </div>
    </>
  );
}
