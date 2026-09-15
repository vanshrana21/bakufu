/** HTTP client for the FastAPI backend.
 *
 * Two modes, chosen by NEXT_PUBLIC_API_BASE_URL:
 *   set   -> live mode. Failures surface as errors; nothing falls back to a fixture.
 *   unset -> fixture mode. Adapters return the synthetic fixtures, labelled
 *            `data_origin: "fixture"` so the UI can say so.
 *
 * The mode is explicit on purpose. A silent fixture fallback on a failed request
 * is the single worst failure this app can have: it would present synthetic
 * numbers as live model output with no visible difference.
 */

/** Trailing slash stripped so `${API_BASE_URL}${path}` never doubles up. */
export const API_BASE_URL: string = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").trim().replace(/\/+$/, "");
export const LIVE_MODE: boolean = API_BASE_URL.length > 0;

/** Default per-request budget. `/prospectivity/heatmap` overrides it — the
 * backend documents 5s warm / 45s cold for that route alone. */
export const DEFAULT_TIMEOUT_MS = 15_000;
export const HEATMAP_TIMEOUT_MS = 60_000;
/** The first `/predict/point` after an API start imports torch/shap and loads
 * the model lazily: measured 26s, against ~0.1s once warm. */
export const PREDICT_POINT_TIMEOUT_MS = 45_000;

/** A request that reached the server and came back non-2xx, or never arrived. */
export class ApiRequestError extends Error {
  readonly endpoint: string;
  readonly status: number | null;
  readonly code: string | null;
  readonly remedy: string | null;
  constructor(message: string, init: { endpoint: string; status?: number | null; code?: string | null; remedy?: string | null }) {
    super(message);
    this.name = "ApiRequestError";
    this.endpoint = init.endpoint;
    this.status = init.status ?? null;
    this.code = init.code ?? null;
    this.remedy = init.remedy ?? null;
  }
}

/** The server answered, but its body cannot be mapped onto the frontend contract.
 * Distinct from ApiRequestError: this is a schema disagreement between the two
 * repos, not a transport or server fault, and the fix is an adapter change or a
 * backend contract change — never a fabricated value. */
export class ContractMismatchError extends Error {
  readonly endpoint: string;
  readonly detail: string;
  constructor(endpoint: string, detail: string) {
    super(`${endpoint}: ${detail}`);
    this.name = "ContractMismatchError";
    this.endpoint = endpoint;
    this.detail = detail;
  }
}

interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  query?: Record<string, string | number | boolean | null | undefined>;
}

/** Combine the caller's signal with a timeout without relying on AbortSignal.any,
 * which is not available in every runtime this builds for. */
function withTimeout(signal: AbortSignal | undefined, timeoutMs: number): { signal: AbortSignal; dispose: () => void } {
  const controller = new AbortController();
  const onAbort = () => controller.abort(signal?.reason);
  if (signal?.aborted) controller.abort(signal.reason);
  else signal?.addEventListener("abort", onAbort, { once: true });
  const timer = setTimeout(() => {
    controller.abort(new DOMException(`Request exceeded ${timeoutMs}ms`, "TimeoutError"));
  }, timeoutMs);
  return {
    signal: controller.signal,
    dispose: () => { clearTimeout(timer); signal?.removeEventListener("abort", onAbort); },
  };
}

function buildUrl(path: string, query: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined) url.searchParams.set(key, String(value));
  }
  return url.toString();
}

/** The backend has three documented error shapes. Turn any of them into one message.
 *   500 -> {error_code, detail, remedy}
 *   422 -> {detail: [{type, loc, msg, input}]}   (FastAPI native)
 *   404 -> {detail: "mine 'Foo' not found..."}
 */
async function readError(response: Response, endpoint: string): Promise<ApiRequestError> {
  let body: unknown = null;
  try { body = await response.json(); } catch { /* non-JSON body; fall through */ }
  const record = (body ?? {}) as Record<string, unknown>;

  if (typeof record.error_code === "string") {
    return new ApiRequestError(String(record.detail ?? record.error_code), {
      endpoint, status: response.status, code: record.error_code,
      remedy: typeof record.remedy === "string" ? record.remedy : null,
    });
  }
  if (Array.isArray(record.detail)) {
    const issues = (record.detail as Array<Record<string, unknown>>)
      .map((issue) => `${Array.isArray(issue.loc) ? issue.loc.join(".") : "?"}: ${String(issue.msg ?? "invalid")}`)
      .join("; ");
    return new ApiRequestError(`Validation failed — ${issues}`, { endpoint, status: response.status, code: "validation_error" });
  }
  if (typeof record.detail === "string") {
    return new ApiRequestError(record.detail, { endpoint, status: response.status });
  }
  return new ApiRequestError(`${response.status} ${response.statusText}`, { endpoint, status: response.status });
}

async function request<T>(method: "GET" | "POST", path: string, options: RequestOptions & { body?: unknown } = {}): Promise<T> {
  if (!LIVE_MODE) {
    throw new ApiRequestError(
      "NEXT_PUBLIC_API_BASE_URL is not set, so no live request can be made.",
      { endpoint: path, remedy: "Add NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 to .env.local and restart the dev server." },
    );
  }
  const { signal, dispose } = withTimeout(options.signal, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  try {
    const response = await fetch(buildUrl(path, options.query), {
      method,
      signal,
      // Model output changes when the backend promotes an artifact; a cached
      // response would keep serving the superseded one.
      cache: "no-store",
      headers: options.body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    if (!response.ok) throw await readError(response, path);
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiRequestError) throw error;
    // A caller-initiated abort must propagate untouched so useEffect cleanup and
    // the usePrediction race guard keep working.
    if (error instanceof DOMException && error.name === "AbortError" && options.signal?.aborted) throw error;
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiRequestError(error.message, { endpoint: path, code: "timeout" });
    }
    throw new ApiRequestError(
      error instanceof Error ? error.message : "Network request failed",
      { endpoint: path, code: "network_error", remedy: `Is the API running at ${API_BASE_URL}?` },
    );
  } finally {
    dispose();
  }
}

export const apiGet = <T>(path: string, options?: RequestOptions): Promise<T> => request<T>("GET", path, options);
export const apiPost = <T>(path: string, body: unknown, options?: RequestOptions): Promise<T> => request<T>("POST", path, { ...options, body });

/** What every page-level loader returns. `origin` is carried separately from the
 * payload so a page can label the surface even when the payload failed to load. */
export interface LoadResult<T> {
  data: T | null;
  error: string | null;
  origin: "live" | "fixture";
}

export const liveResult = <T>(data: T): LoadResult<T> => ({ data, error: null, origin: "live" });
export const fixtureResult = <T>(data: T): LoadResult<T> => ({ data, error: null, origin: "fixture" });
export function failedResult<T>(error: unknown): LoadResult<T> {
  if (error instanceof ContractMismatchError) return { data: null, error: `Contract mismatch — ${error.detail}`, origin: "live" };
  if (error instanceof ApiRequestError) {
    return { data: null, error: error.remedy ? `${error.message} (${error.remedy})` : error.message, origin: "live" };
  }
  return { data: null, error: error instanceof Error ? error.message : "Unknown failure", origin: "live" };
}

// --- shared field helpers -------------------------------------------------
// Used by every adapter so month/date handling cannot drift between them.

/** "2026-09" -> "2026-09-01T00:00:00.000Z". Throws on a malformed month. */
export function monthToIso(month: string): string {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) throw new Error(`Not a YYYY-MM month: ${month}`);
  return new Date(`${month}-01T00:00:00Z`).toISOString();
}

/** "2026-09-09" or a full ISO string -> ISO 8601 with an explicit Z offset.
 * The frontend Timestamp schema is `.datetime({offset:true})`, which rejects a
 * bare date, and the backend sends `forecast_date` as a bare date. */
export function toIsoTimestamp(value: string | null | undefined, fallback: Date = new Date()): string {
  if (!value) return fallback.toISOString();
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date(`${value}T00:00:00Z`).toISOString();
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? fallback.toISOString() : parsed.toISOString();
}

/** Advance "2026-09" by n months. */
export function addMonths(month: string, count: number): string {
  const [year, index] = month.split("-").map(Number);
  const date = new Date(Date.UTC(year!, index! - 1 + count, 1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}
