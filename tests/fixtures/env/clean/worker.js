export default {
  async fetch(request, env) {
    const base = env.API_BASE;
    const hit = await env.CACHE.get("k");
    return new Response(hit || base);
  },
};
