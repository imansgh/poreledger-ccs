"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AssessmentForm } from "./AssessmentForm";
import { AssessmentResults } from "./AssessmentResults";
import { InputCompleteness } from "./InputCompleteness";
import { Notice } from "./Notice";
import { ApiClientError } from "@/lib/api";
import { num } from "@/lib/format";
import {
  documentToDrafts,
  draftsToDocument,
  emptyDraft,
  evaluate,
  fileUrl,
  getExamples,
  isBlockedPreview,
  missingSchemaVersion,
  parseFile,
  problemsFor,
  SCHEMA_VERSION,
  withoutUnknownFields,
  type AssessmentDraft,
  type EvaluationResponse,
  type Problem,
} from "@/lib/assessment";

const MAX_FILE_BYTES = 200_000;
const SAMPLES = 2000;

type Mode = "enter" | "upload" | "example";

/** Read a chosen file as text. It is only ever parsed as data. */
function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

function messageFor(error: unknown): string {
  if (error instanceof ApiClientError) return error.message;
  return "Something went wrong while talking to the screening service.";
}

type Doc = Record<string, unknown>;

const keyOf = (drafts: AssessmentDraft[], base: Doc | null) =>
  JSON.stringify(draftsToDocument(drafts, base));

/**
 * The working area: choose data, review inputs, calculate, read the result.
 * Inputs on the left, results on the right (stacked on a phone, inputs
 * first). A result is shown as outdated the moment its inputs change, and a
 * response that arrives after an edit or a newer run is dropped. The same
 * holds for a file import: a parse that finishes after an edit, a newer
 * import or a change of source is discarded.
 *
 * An imported file is kept as imported: its schema version and anything the
 * form cannot show go back to the backend unchanged, so its problems stay in
 * force until the user corrects them.
 */
export function AssessmentWorkspace() {
  const [drafts, setDrafts] = useState<AssessmentDraft[]>(() => [emptyDraft()]);
  const [selected, setSelected] = useState(0);
  const [mode, setMode] = useState<Mode>("enter");
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState<{ label: string; apply: () => void } | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [response, setResponse] = useState<EvaluationResponse | null>(null);
  const [responseKey, setResponseKey] = useState<string | null>(null);
  const [examples, setExamples] = useState<AssessmentDraft[] | null>(null);
  const [examplesError, setExamplesError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [imported, setImported] = useState(false);
  /** The imported document (its assessments come from the drafts), or null for new or example entries. */
  const [base, setBase] = useState<Doc | null>(null);
  const [importing, setImporting] = useState(false);
  const [importNote, setImportNote] = useState<string | null>(null);
  const generation = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);

  const draft = drafts[selected];
  const synthetic = drafts.some((d) => d.synthetic);
  const currentKey = useMemo(() => keyOf(drafts, base), [drafts, base]);
  const outdated = response !== null && responseKey !== currentKey;
  const upToDate = response !== null && !outdated;
  const errors = problems.filter((p) => p.severity === "error");
  const general = problems.filter((p) => !/^assessments\[\d+\]/.test(p.path));
  const unknownFields = errors.some((p) => p.code === "UNKNOWN_FIELD");
  /**
   * A parser-produced partial preview (conflicting or skipped CSV rows). Its
   * backend marker stays in ``base`` through every edit, so calculation stays
   * blocked until a corrected upload, a fresh assessment or an example
   * replaces it; the backend rejects the marker too.
   */
  const blockedPreview = isBlockedPreview(base);
  const noVersion = !blockedPreview && missingSchemaVersion(base);

  // Move focus to fresh results: on a phone they sit below the form.
  useEffect(() => {
    if (response) document.getElementById("results-heading")?.focus();
  }, [response]);

  /** Replace the inputs, asking first if the user has edited the current ones. */
  function replace(label: string, apply: () => void) {
    if (dirty) setPending({ label, apply });
    else apply();
  }

  function load(next: AssessmentDraft[], fromImport = false, nextBase: Doc | null = null) {
    generation.current += 1;
    setDrafts(next.length ? next : [emptyDraft()]);
    setBase(nextBase);
    setImporting(false);
    setImportNote(null);
    setSelected(0);
    setDirty(false);
    setPending(null);
    setProblems([]);
    setResponse(null);
    setResponseKey(null);
    setError(null);
    setImported(fromImport);
    setBusy(false);
  }

  function edit(next: AssessmentDraft) {
    generation.current += 1;
    setDirty(true);
    setBusy(false);
    setImporting(false);
    setDrafts((all) => all.map((d, i) => (i === selected ? next : d)));
  }

  /** Explicit corrections of an imported file; each is the user's own choice. */
  function correct(nextBase: Doc | null, nextDrafts: AssessmentDraft[] = drafts) {
    generation.current += 1;
    setDirty(true);
    setBusy(false);
    setImporting(false);
    setBase(nextBase);
    setDrafts(nextDrafts);
  }

  async function chooseExamples() {
    setMode("example");
    setError(null);
    setExamplesError(null);
    if (examples) return;
    try {
      setExamples(documentToDrafts(await getExamples()));
    } catch (err) {
      // Shown in the examples panel itself, with a retry, never as endless "Loading".
      setExamplesError(messageFor(err));
    }
  }

  async function onFile(file: File) {
    // An edit, a newer import, a new run or a change of source supersedes this one.
    const gen = ++generation.current;
    setError(null);
    setImportNote(null);
    setBusy(false);
    setFileName(file.name);
    if (file.size > MAX_FILE_BYTES) {
      setImporting(false);
      setProblems([{ path: "", row: null, code: "FILE_TOO_LARGE", severity: "error",
                     message: `The file is ${file.size} bytes; the limit is ${MAX_FILE_BYTES} bytes.` }]);
      return;
    }
    setImporting(true);
    const format = file.name.toLowerCase().endsWith(".csv") ? "csv" : "json";
    try {
      const parsed = await parseFile(format, await readText(file));
      if (gen !== generation.current) return;
      // A blocked import comes only as a marked preview: shown, never evaluated.
      const parsedDoc = parsed.document ?? parsed.preview_document ?? null;
      const next = parsedDoc ? documentToDrafts(parsedDoc) : [];
      if (!next.length) {
        // Nothing editable in the file: keep the current inputs and say why.
        setImporting(false);
        setProblems(parsed.problems);
        setImportNote(`${file.name} was not loaded; your current inputs are unchanged.`);
        return;
      }
      load(next, true, parsedDoc as unknown as Doc);
      setProblems(parsed.problems);
    } catch (err) {
      if (gen !== generation.current) return;
      setImporting(false);
      setError(messageFor(err));
    }
  }

  async function run(target: AssessmentDraft[] = drafts, targetBase: Doc | null = base) {
    if (isBlockedPreview(targetBase)) return; // a partial import is never evaluated
    const gen = ++generation.current;
    const key = keyOf(target, targetBase);
    setBusy(true);
    setImporting(false);
    setError(null);
    try {
      const outcome = await evaluate(draftsToDocument(target, targetBase), SAMPLES);
      if (gen !== generation.current) return;
      if (outcome.ok) {
        setProblems(outcome.data.notices);
        setResponseKey(key);
        setResponse(outcome.data);
      } else {
        setProblems(outcome.problems);
        setResponse(null);
        setResponseKey(null);
      }
    } catch (err) {
      if (gen === generation.current) setError(messageFor(err));
    } finally {
      if (gen === generation.current) setBusy(false);
    }
  }

  function loadAndRun(example: AssessmentDraft) {
    replace(`load ${example.id}`, () => {
      const next = [JSON.parse(JSON.stringify(example)) as AssessmentDraft];
      load(next);
      void run(next, null);
    });
  }

  return (
    <section className="workspace" aria-label="Assessment workspace">
      <div className="workspace-grid">
        <div className="col-inputs stack">
          <section className="panel step" aria-labelledby="step-data">
            <h2 id="step-data">
              <span className="step-no" aria-hidden="true">1</span> Data
            </h2>
            <div className="source-actions" role="group" aria-label="Choose your data">
              <button type="button" className={mode === "enter" ? "" : "secondary"} aria-pressed={mode === "enter"}
                      onClick={() => {
                        setMode("enter");
                        if (synthetic || imported) replace("start a blank assessment", () => load([emptyDraft()]));
                      }}>
                Enter my data
              </button>
              <button type="button" className={mode === "upload" ? "" : "secondary"} aria-pressed={mode === "upload"}
                      onClick={() => {
                        setMode("upload");
                        replace("upload a file", () => fileInput.current?.click());
                      }}>
                Upload a data file
              </button>
              <button type="button" className={mode === "example" ? "" : "secondary"} aria-pressed={mode === "example"}
                      onClick={() => void chooseExamples()}>
                Explore a synthetic example
              </button>
            </div>
            <input ref={fileInput} type="file" accept=".json,.csv,application/json,text/csv"
                   className="sr-only" tabIndex={-1} aria-label="Data file (JSON or CSV)"
                   onChange={(e) => {
                     const file = e.target.files?.[0];
                     if (file) void onFile(file);
                     e.target.value = "";
                   }} />

            {pending ? (
              <div className="confirm" role="alert">
                <p>This will {pending.label} and replace the inputs you edited.</p>
                <div className="actions">
                  <button type="button" onClick={() => { const apply = pending.apply; setPending(null); apply(); }}>
                    Replace my inputs
                  </button>
                  <button type="button" className="secondary" onClick={() => setPending(null)}>
                    Keep my inputs
                  </button>
                </div>
              </div>
            ) : null}

            {mode === "upload" ? (
              <p className="hint">
                JSON or CSV, up to 200 kB.{" "}
                <a href={fileUrl("assessment-template.csv")}>CSV template</a> ·{" "}
                <a href={fileUrl("assessment-template.json")}>JSON template</a>
                {fileName && imported && !importing ? ` · Loaded: ${fileName}` : ""}
              </p>
            ) : null}
            {importing ? <p className="unavailable" role="status">Reading {fileName}...</p> : null}
            {importNote ? <p className="field-error" role="alert">{importNote}</p> : null}
            {blockedPreview ? (
              <Notice tone="stop" title="Calculation is blocked for this file">
                <p>
                  The file has rows the form cannot represent (listed under Review inputs, with
                  row numbers): the preview shows only part of what the file says. Correct the file
                  and upload it again, or start a new assessment or load an example.
                </p>
              </Notice>
            ) : null}

            {mode === "example" ? (
              <div aria-live="polite">
                {examples === null && examplesError ? (
                  <p className="field-error" role="alert">
                    The examples could not be loaded: {examplesError}{" "}
                    <button type="button" className="secondary small" onClick={() => void chooseExamples()}>
                      Try again
                    </button>
                  </p>
                ) : examples === null ? (
                  <p className="unavailable" role="status">Loading examples...</p>
                ) : null}
                <ul className="example-list">
                  {(examples ?? []).map((ex) => (
                    <li key={ex.id}>
                      <div className="example-text">
                        <strong>{(ex.name || ex.id).replace(/^Synthetic example: (.)/, (_m, c: string) => c.toUpperCase())}</strong>
                        <span className="tech nowrap"> {ex.id}</span>
                        <p className="hint">{ex.example?.demonstrates}</p>
                      </div>
                      <div className="example-actions">
                        <button type="button" className="secondary small"
                                aria-label={`Load example ${ex.id}`}
                                onClick={() => replace(`load ${ex.id}`, () => load([JSON.parse(JSON.stringify(ex))]))}>
                          Load
                        </button>
                        <button type="button" className="small"
                                aria-label={`Load and calculate example ${ex.id}`}
                                onClick={() => loadAndRun(ex)}>
                          Load and calculate
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
                <p className="hint">
                  All four are fictional. They show how the model behaves, not real-world accuracy.{" "}
                  <a href={fileUrl("synthetic-examples.csv")}>CSV</a> · <a href={fileUrl("synthetic-examples.json")}>JSON</a>
                </p>
              </div>
            ) : null}

            {drafts.length > 1 ? (
              <div className="draft-picker">
                <h3>{drafts.length} assessments{imported && fileName ? ` from ${fileName}` : ""}</h3>
                <ul className="draft-list">
                  {drafts.map((d, i) => {
                    const count = problemsFor(problems, i).size;
                    return (
                      <li key={i}>
                        <button type="button" className="well-row" aria-current={i === selected}
                                onClick={() => setSelected(i)}>
                          <span className="id nowrap">{d.id || `(no ID, #${i + 1})`}</span>
                          <span className="meta">{count ? `${count} to check` : ""}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : null}
          </section>

          {synthetic ? (
            <section className="demo-banner" role="region" aria-labelledby="synthetic-heading">
              <h2 id="synthetic-heading">Synthetic example data</h2>
              <p>Fictional inputs. Results and exports stay labelled synthetic, also after edits.</p>
              {draft?.example?.demonstrates ? <p className="detail">{draft.example.demonstrates}</p> : null}
              <button type="button" className="secondary small"
                      onClick={() => { setMode("enter"); replace("start your own assessment", () => load([emptyDraft()])); }}>
                Start my own assessment
              </button>
            </section>
          ) : null}

          {draft ? (
            <form className="panel step" aria-labelledby="step-review" noValidate
                  onSubmit={(e) => { e.preventDefault(); if (!busy && !upToDate) void run(); }}>
              <h2 id="step-review">
                <span className="step-no" aria-hidden="true">2</span> Review inputs
                {drafts.length > 1 ? <span className="tech"> ({selected + 1} of {drafts.length})</span> : null}
                {draft.synthetic ? <span className="tag tag-synthetic">SYNTHETIC</span> : null}
              </h2>
              {general.length ? (
                <Notice tone={general.some((p) => p.severity === "error") ? "advisory" : "plain"}
                        title={errors.length ? "Please check" : "Notes"}>
                  <ul>
                    {general.map((p, i) => (
                      <li key={i}>
                        {p.row ? `Row ${p.row}: ` : ""}
                        {p.message}
                      </li>
                    ))}
                  </ul>
                </Notice>
              ) : null}
              {unknownFields || noVersion ? (
                <div className="actions" role="group" aria-label="Correct the imported file">
                  {unknownFields ? (
                    <button type="button" className="secondary small"
                            onClick={() => { const fixed = withoutUnknownFields(base, drafts); correct(fixed.base, fixed.drafts); }}>
                      Remove unrecognised fields
                    </button>
                  ) : null}
                  {noVersion ? (
                    <button type="button" className="secondary small"
                            onClick={() => correct({ ...(base ?? {}), schema_version: SCHEMA_VERSION })}>
                      Declare the file as {SCHEMA_VERSION}
                    </button>
                  ) : null}
                </div>
              ) : null}
              <InputCompleteness draft={draft} index={selected} />
              <AssessmentForm draft={draft} index={selected} onChange={edit}
                              errors={problemsFor(problems, selected)} />
              <div className="calc-bar">
                <button type="submit" className="primary" disabled={busy || importing || upToDate || blockedPreview}>
                  {busy ? "Calculating..." : upToDate ? "Result is up to date" : drafts.length > 1 ? "Calculate all" : "Calculate"}
                </button>
                {errors.length ? (
                  <p className="field-error" role="alert">
                    {errors.length} input problem(s) to fix. Your entries are kept.
                  </p>
                ) : null}
                {upToDate ? (
                  <a href="#results-heading" className="jump"
                     onClick={(e) => { e.preventDefault(); document.getElementById("results-heading")?.focus(); }}>
                    View result summary
                  </a>
                ) : null}
              </div>
            </form>
          ) : null}
        </div>

        <div className="col-results stack" aria-live="polite" aria-busy={busy}>
          {error ? (
            <Notice tone="stop" title="Service problem">
              <p>{error} Your inputs are kept; try again.</p>
            </Notice>
          ) : null}
          {busy ? (
            <div className="panel">
              <p className="unavailable" role="status">
                Calculating {num(SAMPLES, 0)} realisations per water-table scenario for{" "}
                {drafts.length} assessment(s)...
              </p>
            </div>
          ) : null}
          {response ? <AssessmentResults response={response} outdated={outdated} /> : null}
          {!response && !busy && !error ? (
            <div className="panel empty-results">
              <h2>
                <span className="step-no" aria-hidden="true">3</span> Results
              </h2>
              <p>Results appear here after you calculate.</p>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
