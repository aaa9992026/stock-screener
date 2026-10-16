// Poll only an explicit cache warmup, within the existing request time budget.
export async function requestRanking(request, {
  timeoutMs, now = Date.now, sleep = ms => new Promise(resolve => setTimeout(resolve, ms)),
}) {
  const deadline = now() + timeoutMs;
  while (true) {
    try {
      return await request(Math.max(1, deadline - now()));
    } catch (error) {
      if (error?.response?.status !== 503 || error?.response?.data?.detail?.code !== "RANKING_WARMING") throw error;
      const retry = Number(error.response.headers?.["retry-after"]);
      const delay = Math.min(5000, Math.max(1000, Number.isFinite(retry) && retry > 0 ? retry * 1000 : 2000));
      if (now() + delay >= deadline) throw error;
      await sleep(delay);
    }
  }
}
