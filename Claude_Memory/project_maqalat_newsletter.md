---
name: Maqalat Newsletter (Resend)
description: Newsletter capture wired to Resend for Maqalat — key learnings and the API path chosen.
type: reference
originSessionId: 14a723a5-c3b8-4b2e-9b1e-b55d65dd193f
---
Applied 2026-09-01. Live end-to-end on maqalat.org.

## Provider: Resend
- Free tier: 3,000 emails/month, 100/day, 1 audience
- **Default audience "General" auto-created** on signup — no need to create manually
- Audience ID: `66223790-63bd-4fae-9d0f-6133b498d1de` (this project)
- Get audience ID via API (dashboard UI doesn't expose it prominently):
  ```
  curl -H "Authorization: Bearer <full-key>" https://api.resend.com/audiences
  ```

## Permission trap
- Resend has two API key types: **Sending access** vs **Full access**
- Sending-only keys return `401: "This API key is restricted to only send emails"` on any non-email endpoint (audiences, contacts, etc.)
- For newsletter contact management → **Full access is mandatory**
- Onboarding wizard defaults to Sending — must delete + recreate with Full access

## File layout in Maqalat
- `app/api/newsletter/route.ts` — POST endpoint, uses `resend.contacts.create()`. Idempotent ("already exists" treated as success). Returns 503 if env vars missing (graceful fallback).
- `components/NewsletterSignup.tsx` — client component, bilingual via `useTranslations('newsletter')`, `card` + `inline` variants
- Wired in `app/[locale]/[slug]/page.tsx` before comments section with `source={`article:${slug}`}`
- Strings in `messages/{ar,en}.json` → `newsletter` namespace

## Env vars on Vercel (Production + Preview)
```
RESEND_API_KEY=re_...          # Secret (server-only, not NEXT_PUBLIC_)
RESEND_AUDIENCE_ID=<uuid>       # Config
```

## Testing after deploy
```bash
# Subscribe (200 ok)
curl -X POST https://maqalat.org/api/newsletter \
  -H "Content-Type: application/json" \
  -d '{"email":"t@example.com","locale":"ar","source":"test"}'

# Verify count in audience
curl -H "Authorization: Bearer <key>" \
  https://api.resend.com/audiences/<audience_id>/contacts | grep -oE '"email"' | wc -l
```

## Future work (not done yet)
- **Domain verification** for `maqalat.org` in Resend Domains section (DNS: SPF, DKIM, DMARC via Cloudflare). Needed before sending broadcast emails from `nashra@maqalat.org` instead of `onboarding@resend.dev`.
- **Broadcast composer** in Resend UI or via API — send weekly to whole audience.
- **Firestore backup** of contacts (currently Resend is sole source of truth).
- **Add NewsletterSignup to Footer** (currently only in article pages).
