/** Empty = same-origin `/api` (Vite proxy in dev). Set `VITE_API_BASE` for split deploys. */
const rawBase = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function buildUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${rawBase}${p}`;
}

export async function fetchJson<T>(
  path: string,
  init?: RequestInit & { json?: unknown }
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.json !== undefined ? { "Content-Type": "application/json" } : {}),
  };
  if (init?.headers) {
    const h = new Headers(init.headers);
    h.forEach((v, k) => {
      headers[k] = v;
    });
  }

  const res = await fetch(buildUrl(path), {
    ...init,
    headers,
    body:
      init?.json !== undefined ? JSON.stringify(init.json) : init?.body,
  });

  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    let msg = res.statusText;
    if (typeof data === "object" && data !== null && "detail" in data) {
      const d = (data as { detail: unknown }).detail;
      msg = typeof d === "string" ? d : JSON.stringify(d);
    }
    throw new ApiError(msg || res.statusText, res.status, data);
  }

  return data as T;
}
