import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, createRecommendations } from "./api/client";
import type { RecommendationRequest, RecommendationResponse } from "./api/types";
import { LocationPicker } from "./components/LocationPicker";
import { RestaurantCard } from "./components/RestaurantCard";
import {
  initialForm,
  summaryOf,
  toRequest,
  validateForm,
  type FormErrors,
  type FormValues,
} from "./form";
import { useBudgetBands, useCuisines } from "./hooks/useMetadata";

interface SearchResult {
  response: RecommendationResponse;
  request: RecommendationRequest;
}

interface SearchError {
  code: string;
  message: string;
  requestId?: string | null;
}

function describeError(error: unknown): SearchError {
  if (error instanceof ApiError) {
    const messages: Record<string, string> = {
      NO_MATCHES: "No restaurants matched all of these preferences. Your filters have not been changed.",
      VALIDATION_ERROR: "Some preferences could not be accepted. Review the highlighted fields and search again.",
      DATASET_UNAVAILABLE: "Restaurant data is temporarily unavailable. Your preferences are saved here; please retry shortly.",
      RATE_LIMITED: "There have been too many requests. Wait a moment, then try again.",
    };
    return {
      code: error.code,
      requestId: error.requestId,
      message: messages[error.code] ?? "The service could not complete this search. Please try again shortly.",
    };
  }
  return {
    code: "NETWORK_ERROR",
    message: "We couldn't reach the recommendation service. Check your connection and try again.",
  };
}

function BrandMark() {
  return <svg viewBox="0 0 32 32" aria-hidden="true">
    <path d="M8 5v8M5.5 5v5.5c0 3 5 3 5 0V5M8 13v14M22 5v22M22 5c-5 3-5.5 11 0 12" />
  </svg>;
}

function LocationPin() {
  return <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
    <circle cx="12" cy="10" r="2.5" />
  </svg>;
}

function ResultsMark() {
  return <svg className="results-mark" viewBox="0 0 90 66" aria-hidden="true">
    <path d="M14 8h50a10 10 0 0 1 10 10v22a10 10 0 0 1-10 10H42L28 61l3-11H14A10 10 0 0 1 4 40V18A10 10 0 0 1 14 8Z" />
    <path d="M39 37s-12-7-12-15c0-7 9-9 12-3 3-6 12-4 12 3 0 8-12 15-12 15Z" />
    <path className="leaf" d="M70 54c7-1 12 1 15 6-7 2-12 0-15-6ZM73 12c3-6 7-8 12-7-1 7-5 10-12 7Z" />
  </svg>;
}

export function App() {
  const [form, setForm] = useState<FormValues>(initialForm);
  const [errors, setErrors] = useState<FormErrors>({});
  const [retry, setRetry] = useState(0);
  const [cuisineQuery, setCuisineQuery] = useState("");
  const [phase, setPhase] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [submitted, setSubmitted] = useState<RecommendationRequest | null>(null);
  const [searchError, setSearchError] = useState<SearchError | null>(null);
  const [notice, setNotice] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const activeRequest = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const bands = useBudgetBands(retry);
  const cuisineResource = useCuisines(form.location, retry);
  const availableCuisines = cuisineResource.data?.values ?? [];
  const metadataBlocked = bands.status !== "ready" || (Boolean(form.location) && cuisineResource.status !== "ready");
  const stale = result !== null && JSON.stringify(result.request) !== JSON.stringify(toRequest(form));

  useEffect(() => () => {
    sequence.current += 1;
    activeRequest.current?.abort();
  }, []);

  function edit(patch: Partial<FormValues>, message = "") {
    sequence.current += 1;
    activeRequest.current?.abort();
    activeRequest.current = null;
    setPhase(result ? "success" : "idle");
    setSearchError(null);
    setErrors({});
    setForm((previous) => ({ ...previous, ...patch }));
    setNotice(message);
    setAnnouncement(message || (phase === "loading" ? "Search cancelled. Search again with your updated preferences." : ""));
  }

  function changeLocation(value: string, selected: boolean) {
    const changed = value !== form.location;
    edit(
      {
        locationQuery: value,
        location: selected ? value : "",
        ...(changed ? { cuisines: [] } : {}),
      },
      changed && form.cuisines.length ? "Cuisine selections cleared for the new locality." : "",
    );
    if (changed) setCuisineQuery("");
  }

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (activeRequest.current) return;
    const validation = validateForm(form, availableCuisines);
    setErrors(validation);
    if (Object.keys(validation).length) {
      setAnnouncement("Please check your preferences.");
      const targets: Partial<Record<keyof FormValues, string>> = {
        location: "location",
        customMaximum: "custom-maximum",
        cuisines: "cuisine-search",
        preferences: "preferences",
      };
      const first = Object.keys(validation)[0] as keyof FormValues;
      document.getElementById(targets[first] ?? "location")?.focus();
      return;
    }
    if (metadataBlocked) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    const current = ++sequence.current;
    const request = toRequest(form);
    setSubmitted(request);
    setPhase("loading");
    setSearchError(null);
    setNotice("");
    setAnnouncement("Finding restaurants that match your preferences.");
    try {
      const response = await createRecommendations(request, controller.signal);
      if (current !== sequence.current || controller.signal.aborted) return;
      if (response.recommendations.length === 0) {
        throw new ApiError("No matches.", 404, response.request_id, "NO_MATCHES");
      }
      setResult({ response, request });
      setPhase("success");
      setAnnouncement(`${response.recommendations.length} restaurant${response.recommendations.length === 1 ? "" : "s"} found in ${request.location}.`);
    } catch (error) {
      if (current !== sequence.current || controller.signal.aborted) return;
      setSearchError(describeError(error));
      setPhase("error");
      setAnnouncement("");
      if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
        const fieldMap: Record<string, keyof FormValues> = {
          location: "location",
          budget: "customMaximum",
          cuisines: "cuisines",
          minimum_rating: "minimumRating",
          additional_preferences: "preferences",
          limit: "limit",
        };
        const fieldErrors: FormErrors = {};
        if (Array.isArray(error.details.fields)) {
          for (const field of error.details.fields) {
            if (field && typeof field === "object" && "path" in field && typeof field.path === "string") {
              const key = fieldMap[field.path.split(".")[1]];
              if (key) fieldErrors[key] = "Please review this value and try again.";
            }
          }
        }
        setErrors(fieldErrors);
      }
    } finally {
      if (current === sequence.current) activeRequest.current = null;
    }
  }

  const budgetChoices = bands.data?.bands ?? [];
  const filteredCuisines = availableCuisines.filter((value) => value.toLocaleLowerCase().includes(cuisineQuery.toLocaleLowerCase()));

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to search</a>
    <header className="site-header">
      <a className="brand" href="/" aria-label="DineGenie restaurant recommendations home"><span className="brand-mark"><BrandMark /></span><span>DineGenie</span></a>
      <span className="coverage"><LocationPin />Bengaluru</span>
    </header>
    <main id="main-content">
      <section className="intro" aria-labelledby="page-title">
        <div><p className="eyebrow">AI-powered dining recommendations</p><h1 id="page-title">Find your next great meal.</h1><p className="intro-copy">Tell us what you’re in the mood for — we’ll handle the rest.</p></div>
        <p className="intro-note"><span aria-hidden="true">✦</span> Personal picks, grounded in restaurant data.</p>
      </section>
      <div className="workspace">
        <section className="search-panel" aria-labelledby="search-title">
          <div className="panel-heading"><span className="step-number">01</span><div><p className="eyebrow">Your preferences</p><h2 id="search-title">What are you looking for?</h2></div></div>
          <form noValidate onSubmit={(event) => void submit(event)}>
            <LocationPicker value={form.locationQuery} error={errors.location} onType={(value) => changeLocation(value, false)} onSelect={(value) => changeLocation(value, true)} />
            <fieldset className="field budget-field">
              <legend>Budget for two <span className="required-label">INR</span></legend>
              <div className="budget-options">{budgetChoices.map((band) => <label key={band.id} className="budget-option">
                <input type="radio" name="budget" value={band.id} checked={form.budget === band.id} onChange={() => edit({ budget: band.id })} />
                <span><i aria-hidden="true">₹</i><strong>{band.id[0].toUpperCase() + band.id.slice(1)}</strong><small>{band.maximum_inclusive === null ? `Over ₹${band.minimum_exclusive?.toLocaleString("en-IN")}` : band.minimum_exclusive === null ? `Up to ₹${band.maximum_inclusive.toLocaleString("en-IN")}` : `₹${(band.minimum_exclusive + 1).toLocaleString("en-IN")}–${band.maximum_inclusive.toLocaleString("en-IN")}`}</small></span>
              </label>)}</div>
              {bands.status === "loading" && <p className="field-help">Loading budget options…</p>}
              {bands.status === "error" && <p className="field-error" role="alert">Budget options could not load. <button type="button" className="text-button" onClick={() => setRetry((count) => count + 1)}>Retry options</button></p>}
              <label className="custom-toggle"><input type="radio" name="budget" value="custom" checked={form.budget === "custom"} onChange={() => edit({ budget: "custom" })} />Set my own maximum</label>
              {form.budget === "custom" && <div className="custom-budget"><label htmlFor="custom-maximum">Maximum amount in INR</label><input id="custom-maximum" type="number" inputMode="numeric" min="1" max="100000" step="1" placeholder="e.g. 900" value={form.customMaximum} onChange={(event) => edit({ customMaximum: event.target.value })} aria-invalid={Boolean(errors.customMaximum)} aria-describedby="custom-help" /><p id="custom-help" className={errors.customMaximum ? "field-error" : "field-help"} role={errors.customMaximum ? "alert" : undefined}>{errors.customMaximum ?? "This maximum replaces the budget band."}</p></div>}
              {form.budget !== "custom" && errors.customMaximum && <p className="field-error" role="alert">{errors.customMaximum}</p>}
            </fieldset>
            <fieldset className="field cuisine-field">
              <legend>Cuisines <span className="optional-label">Optional</span></legend><p id="cuisine-help" className="field-help">Select one or more cuisines</p>
              {!form.location ? <p className="metadata-placeholder">Choose a locality to explore its cuisines.</p> : cuisineResource.status === "loading" ? <p className="metadata-placeholder">Loading cuisines for {form.location}…</p> : cuisineResource.status === "error" ? <p className="field-error" role="alert">Cuisines could not load. <button type="button" className="text-button" onClick={() => setRetry((count) => count + 1)}>Retry cuisines</button></p> : <>
                <label className="sr-only" htmlFor="cuisine-search">Search cuisines</label><input id="cuisine-search" type="search" placeholder="Search cuisines" value={cuisineQuery} onChange={(event) => setCuisineQuery(event.target.value)} aria-describedby="cuisine-help" />
                <div className="cuisine-options">{filteredCuisines.map((cuisine) => <label key={cuisine} className="cuisine-option"><input type="checkbox" checked={form.cuisines.includes(cuisine)} disabled={!form.cuisines.includes(cuisine) && form.cuisines.length >= 10} onChange={() => edit({ cuisines: form.cuisines.includes(cuisine) ? form.cuisines.filter((value) => value !== cuisine) : [...form.cuisines, cuisine] })} /><span>{cuisine}</span></label>)}</div>
                {filteredCuisines.length === 0 && <p className="field-help">No cuisines match this search.</p>}
                {form.cuisines.length > 0 && <div className="selected-cuisines"><span>{form.cuisines.length}/10 selected</span><button type="button" className="text-button" onClick={() => edit({ cuisines: [] })}>Clear</button></div>}
              </>}
              {errors.cuisines && <p className="field-error" role="alert">{errors.cuisines}</p>}
            </fieldset>
            <div className="field-pair">
              <div className="field"><label htmlFor="minimum-rating">Minimum rating</label><select id="minimum-rating" value={form.minimumRating} onChange={(event) => edit({ minimumRating: event.target.value })}><option value="any">Any rating</option>{Array.from({ length: 51 }, (_, index) => (index / 10).toFixed(1)).map((rating) => <option key={rating} value={rating}>{rating}+ / 5</option>)}</select>{errors.minimumRating && <p className="field-error" role="alert">{errors.minimumRating}</p>}</div>
              <div className="field"><label htmlFor="result-count">Number of results</label><select id="result-count" value={form.limit} onChange={(event) => edit({ limit: event.target.value })}>{Array.from({ length: 10 }, (_, index) => index + 1).map((value) => <option key={value} value={value}>{value} {value === 1 ? "restaurant" : "restaurants"}</option>)}</select>{errors.limit && <p className="field-error" role="alert">{errors.limit}</p>}</div>
            </div>
            <div className="field"><label htmlFor="preferences">Additional preferences <span className="optional-label">Optional</span></label><textarea id="preferences" rows={3} maxLength={300} value={form.preferences} placeholder="e.g. Family-friendly, online ordering" onChange={(event) => edit({ preferences: event.target.value })} aria-describedby="preferences-help preferences-count" aria-invalid={Boolean(errors.preferences)} /><div className="textarea-caption"><p className="field-help" id="preferences-help">We’ll flag preferences the data cannot verify.</p><span id="preferences-count">{form.preferences.length}/300</span></div>{errors.preferences && <p className="field-error" role="alert">{errors.preferences}</p>}</div>
            {notice && <p className="form-notice">{notice}</p>}
            <button className="primary-button" type="submit" disabled={phase === "loading" || metadataBlocked}>{phase === "loading" ? "Finding your matches…" : "Find Restaurants"}<span aria-hidden="true">→</span></button>
            {phase === "loading" && <button className="text-button cancel-button" type="button" onClick={() => edit({}, "Search cancelled. Your preferences are kept.")}>Cancel search</button>}
            {phase === "success" && result && !stale && <a className="jump-link" href="#results-title">View {result.response.recommendations.length} result{result.response.recommendations.length === 1 ? "" : "s"} ↓</a>}
            <p className="submit-note">Every search respects your selected filters.</p>
          </form>
        </section>
        <section className="results-panel" aria-labelledby="results-title" aria-busy={phase === "loading"}>
          <div className="results-heading"><div><p className="eyebrow">Your recommendations</p><h2 id="results-title" tabIndex={-1}>{phase === "success" && result ? `${result.response.recommendations.length} ${result.response.recommendations.length === 1 ? "restaurant matches" : "restaurants match"} your preferences` : "Your best matches will appear here"}</h2>{phase === "success" && result && <span className="ai-pill">✦ AI-sorted</span>}</div><ResultsMark /></div>
          {phase === "loading" ? <div className="empty-state loading-state"><span className="loading-orbit" aria-hidden="true">✦</span><h3>Building your shortlist</h3><p>Checking locality, cuisine, budget and rating for the strongest matches.</p><div className="loading-line" aria-hidden="true" /></div> : phase === "error" && searchError ? <div className="error-state" role="alert">
            <span className="state-icon" aria-hidden="true">{searchError.code === "NO_MATCHES" ? "↗" : "!"}</span><h3>{searchError.code === "NO_MATCHES" ? "No exact matches this time." : "Let’s try that again."}</h3><p>{searchError.message}</p>
            {submitted && <p className="applied-summary"><strong>Your search</strong>{summaryOf(submitted)}</p>}
            {searchError.code === "NO_MATCHES" ? <div className="refinements"><h4>A few changes you could try</h4><p>Choose a change, review your preferences, then search again.</p>{form.cuisines.length > 0 && <button type="button" onClick={() => edit({ cuisines: [] }, "Cuisine filter cleared. Select Find Restaurants to search again.")}>Try any cuisine</button>}{form.minimumRating !== "any" && <button type="button" onClick={() => edit({ minimumRating: "any" }, "Minimum rating removed. Select Find Restaurants to search again.")}>Try any rating</button>}<button type="button" onClick={() => document.querySelector<HTMLInputElement>('input[name="budget"]:checked')?.focus()}>Review budget</button><button type="button" onClick={() => document.getElementById("location")?.focus()}>Change locality</button></div> : <button type="button" className="secondary-button" onClick={() => void submit()} disabled={metadataBlocked}>Try search again</button>}
            {searchError.requestId && <details className="technical-details"><summary>Support details</summary><p>Request reference: {searchError.requestId}</p></details>}
          </div> : result ? <>
            {stale && <p className="stale-notice">Preferences changed. Search again to update this shortlist.</p>}<p className="search-summary">{summaryOf(result.request)}</p>
            {result.response.meta.ranking_mode === "llm_assisted" && <p className="ranking-note">AI-assisted ordering with source-checked explanations.</p>}{result.response.meta.ranking_mode === "deterministic_fallback" && <p className="ranking-note">AI assistance is unavailable right now. These matches use our standard ranking and respect all your filters.</p>}{result.response.meta.ranking_mode === "llm_assisted" && result.response.summary && <p className="recommendation-summary">{result.response.summary}</p>}
            <ol className="restaurant-list">{result.response.recommendations.map((restaurant, index) => <RestaurantCard key={restaurant.restaurant_id} restaurant={restaurant} rank={index + 1} />)}</ol>
            <details className="technical-details"><summary>About these recommendations</summary><p>Ranked by how well the restaurant data matches your preferences. Prices and ratings come from a static snapshot; confirm current details with the restaurant.</p><p>Snapshot version: <code>{result.response.meta.dataset_version}</code></p><p>{result.response.meta.candidate_count} candidates considered{result.response.meta.candidate_limit_applied ? " (search limit reached)" : ""}.</p><p>Applied filter relaxations: {result.response.meta.filters_relaxed.length ? result.response.meta.filters_relaxed.join(", ") : "None"}.</p><p>Request reference: <code>{result.response.request_id}</code></p></details>
          </> : <div className="empty-state"><span className="empty-mark" aria-hidden="true">✦</span><p className="eyebrow">A thoughtful shortlist</p><h3>Ready when you are.</h3><p>Fine-tune your preferences, then let DineGenie find restaurants that fit.</p><div className="promise-grid"><div><span aria-hidden="true">01</span><strong>Made to match</strong><p>Your selected filters guide every result.</p></div><div><span aria-hidden="true">02</span><strong>Reasons included</strong><p>See why each restaurant earned its place.</p></div></div></div>}
        </section>
      </div>
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">{announcement}</p>
    </main>
    <footer className="site-footer"><strong>DineGenie uses AI to personalize recommendations.</strong><span aria-hidden="true">•</span><p>Always verify details directly with the restaurant.</p></footer>
  </div>;
}
