import { supabase } from "./supabase";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase().auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Call the FitFindr API. Throws ApiError with a message that is safe to show. */
export async function api<T>(
  path: string,
  init: { method?: string; json?: unknown; form?: FormData; signal?: AbortSignal } = {},
): Promise<T> {
  const headers: Record<string, string> = await authHeader();
  let body: BodyInit | undefined;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  } else if (init.form) {
    body = init.form;
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: init.method || (body ? "POST" : "GET"),
      headers,
      body,
      signal: init.signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("We couldn't reach FitFindr. Check your connection and try again.", 0);
  }
  if (!res.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(message, res.status);
  }
  return (await res.json()) as T;
}
