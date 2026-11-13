function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function authorized(request, env) {
  const value = request.headers.get("authorization") || "";
  return value === `Bearer ${env.D1_PROXY_TOKEN}` && Boolean(env.D1_PROXY_TOKEN);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "POST" || !url.pathname.startsWith("/api/")) {
      return json({ success: false, error: "not found" }, 404);
    }
    if (!authorized(request, env)) return json({ success: false, error: "unauthorized" }, 401);

    try {
      const body = await request.json();
      if (url.pathname === "/api/query") {
        if (typeof body.query !== "string" || !Array.isArray(body.params || [])) {
          return json({ success: false, error: "query and params are required" }, 400);
        }
        const params = body.params || [];
        const prepared = env.DB.prepare(body.query);
        const result = await (params.length ? prepared.bind(...params) : prepared).all();
        return json({ success: result.success, results: result.results || [], meta: result.meta || {} });
      }
      if (url.pathname === "/api/batch") {
        if (!Array.isArray(body.statements) || body.statements.length < 1 || body.statements.length > 50) {
          return json({ success: false, error: "batch must contain 1–50 statements" }, 400);
        }
        const statements = body.statements.map((item) => {
          if (typeof item.query !== "string" || !Array.isArray(item.params || [])) throw new Error("invalid statement");
          const params = item.params || [];
          const prepared = env.DB.prepare(item.query);
          return params.length ? prepared.bind(...params) : prepared;
        });
        const results = await env.DB.batch(statements);
        return json({ success: true, results: results.map((item) => ({ results: item.results || [], meta: item.meta || {} })) });
      }
      if (url.pathname === "/api/script") {
        if (typeof body.script !== "string" || body.script.length > 100_000) {
          return json({ success: false, error: "script is invalid or too long" }, 400);
        }
        const result = await env.DB.exec(body.script);
        return json({ success: true, results: [], meta: result });
      }
      return json({ success: false, error: "not found" }, 404);
    } catch (error) {
      return json({ success: false, error: String(error?.message || error).slice(0, 500) }, 400);
    }
  },
};
