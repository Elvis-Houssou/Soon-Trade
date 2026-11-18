const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
  ) {
    super(code);
  }
}

/**
 * Appel à l'API SOON TRADE. La session voyage dans un cookie HttpOnly posé par
 * l'API : le code du navigateur n'y a jamais accès et ne stocke aucun jeton.
 */
export async function api<T = void>(path: string, body?: unknown, method = body ? "POST" : "GET"): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      credentials: "include",
      // Pour un FormData, le navigateur pose lui-même l'en-tête multipart et sa frontière.
      headers: body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network_error");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(response.status, payload?.error?.code ?? "unknown_error");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
