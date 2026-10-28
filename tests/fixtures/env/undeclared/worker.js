export default {
  async fetch(request, env) {
    const row = await env.DB.prepare("select 1").first(); // DB is never declared in wrangler.toml
    return new Response(JSON.stringify(row) + env.API_BASE);
  },
};
