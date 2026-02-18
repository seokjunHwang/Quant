const API_BASE = "/api/v1";

export async function fetchAPI(path: string, options?: RequestInit) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export async function postAPI(path: string, body: unknown) {
  return fetchAPI(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteAPI(path: string) {
  return fetchAPI(path, { method: "DELETE" });
}
