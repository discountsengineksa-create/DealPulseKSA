/**
 * DealPulse — Edge enrichment Worker
 * ====================================
 * Intercepts POST /api/v1/track* requests, enriches them with Cloudflare's
 * geo/network signals, hashes the visitor's IP (daily-rotated salt), then
 * forwards a clean request to the Railway origin.
 *
 * Responsibilities:
 *   1. Extract Cloudflare's geo + network signals (req.cf.*).
 *   2. Hash the visitor's IP so the origin never sees raw IPs (PDPL).
 *   3. Compute a stable User-Agent hash for repeat-visitor stitching.
 *   4. Surface bot-management signals (cf.botManagement.score) downstream.
 *   5. Forward enriched request to Railway in a single fetch().
 *
 * Failure mode: any error inside the Worker is non-fatal — the request
 * still reaches the origin (without enrichment) and the FastAPI handler
 * gracefully fills NULLs where the x-dp-* headers are missing.
 */

export interface Env {
  ORIGIN_BASE: string;
  LOG_LEVEL: "debug" | "info" | "warn";
  IP_HASH_SALT: string; // Cloudflare secret
}

interface CFExtras {
  asOrganization?: string;
  asn?: number;
  botManagement?: { score?: number; verifiedBot?: boolean };
  city?: string;
  country?: string;
  region?: string;
  regionCode?: string;
  postalCode?: string;
  latitude?: string;
  longitude?: string;
  timezone?: string;
}

/**
 * Daily-rotating salt key — combines the secret with today's UTC date so
 * the effective hashing key changes at 00:00 UTC without manual rotation.
 * Same visitor on the same day = same hash (good for unique-visitor count).
 * Same visitor on a different day = different hash (forward-secrecy).
 */
function dailySaltKey(secret: string): string {
  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  return `${secret}:${today}`;
}

async function sha256Hex(input: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function classifyDevice(ua: string): string {
  const u = (ua || "").toLowerCase();
  if (!u || u === "-") return "unknown";
  if (/bot|crawl|spider|slurp|preview|monitor|curl|wget|python-requests|axios|okhttp/.test(u))
    return "bot";
  if (/iphone|android(?!.*tablet)|mobile/.test(u)) return "mobile";
  if (/ipad|tablet/.test(u)) return "tablet";
  return "desktop";
}

export default {
  async fetch(req: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);

    // نُثري طلبات /api/v1/track* (تتبّع) و /go/* (تحويل الأفلييت + bot challenge).
    // أي شيء آخر يمر بدون تعديل.
    const isEnriched =
      url.pathname.startsWith("/api/v1/track") || url.pathname.startsWith("/go/");
    if (!isEnriched) {
      return fetch(`${env.ORIGIN_BASE}${url.pathname}${url.search}`, req);
    }

    try {
      const cf = ((req as unknown) as { cf?: CFExtras }).cf || {};

      // IP الخام — يُستخدم فقط للـ hashing، لا يُمرَّر للأصل
      const rawIp =
        req.headers.get("cf-connecting-ip") ||
        req.headers.get("x-real-ip") ||
        "0.0.0.0";

      const userAgent = req.headers.get("user-agent") || "-";

      // Hash IP بـ salt يومي
      const ipHash = await sha256Hex(`${rawIp}|${dailySaltKey(env.IP_HASH_SALT)}`);
      // Hash UA بدون salt (مستقر عبر الأيام للـ fingerprint stitching)
      const uaHash = await sha256Hex(userAgent);

      // بناء headers مُثراة
      const enriched = new Headers(req.headers);
      enriched.set("x-dp-event-id", crypto.randomUUID());
      enriched.set("x-dp-ip-hash", ipHash);
      enriched.set("x-dp-ua-hash", uaHash);
      enriched.set("x-dp-country", cf.country || "");
      enriched.set("x-dp-region", cf.regionCode || cf.region || "");
      enriched.set("x-dp-city", cf.city || "");
      enriched.set("x-dp-postal", cf.postalCode || "");
      enriched.set("x-dp-lat", cf.latitude || "");
      enriched.set("x-dp-lng", cf.longitude || "");
      enriched.set("x-dp-asn", (cf.asn ?? "").toString());
      enriched.set("x-dp-isp", cf.asOrganization || "");
      enriched.set("x-dp-device", classifyDevice(userAgent));
      enriched.set("x-dp-bot-score", (cf.botManagement?.score ?? "").toString());
      enriched.set("x-dp-verified-bot", cf.botManagement?.verifiedBot ? "1" : "0");

      // إزالة headers الـ IP الخام من الطلب الموجَّه للأصل (PDPL)
      enriched.delete("cf-connecting-ip");
      enriched.delete("x-real-ip");
      enriched.delete("x-forwarded-for");

      const upstream = await fetch(`${env.ORIGIN_BASE}${url.pathname}${url.search}`, {
        method: req.method,
        headers: enriched,
        body: req.body,
        redirect: "manual",
      });

      return upstream;
    } catch (err) {
      // أي خطأ في الإثراء = لا تُعطّل الطلب، حوّل خام للأصل
      if (env.LOG_LEVEL !== "warn") {
        console.error("edge enrichment error", err);
      }
      return fetch(`${env.ORIGIN_BASE}${url.pathname}${url.search}`, req);
    }
  },
};
