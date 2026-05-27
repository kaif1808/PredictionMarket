export async function apiGet(path) {
  const res = await fetch(path, {
    credentials: "include"
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `GET ${path} failed`);
  }
  return res.json();
}

export async function apiPost(path, body, auth) {
  const headers = { "Content-Type": "application/json" };
  if (auth && auth.user && auth.pass) {
    headers.Authorization = `Basic ${btoa(`${auth.user}:${auth.pass}`)}`;
  }
  const res = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers,
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `POST ${path} failed`);
  }
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}
