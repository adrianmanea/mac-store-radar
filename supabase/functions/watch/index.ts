// Edge Function: add/remove a discovered candidate to/from the watch list.
//
// The SPA holds only the anon key (read-only via RLS), so the "Track" button calls this
// instead of writing directly. The function runs with the service role (auto-injected as
// a reserved secret) to flip the flag. Callers must present a valid project key (the SPA
// sends its anon key), so it's gated to the app, not open to the world.

import { createClient } from 'jsr:@supabase/supabase-js@2'

const cors = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: cors })

  try {
    const { keyword, action } = await req.json()
    if (!keyword || (action !== 'add' && action !== 'remove')) {
      return json({ error: "expected { keyword, action: 'add'|'remove' }" }, 400)
    }

    const db = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
    )

    if (action === 'add') {
      await db
        .from('niches')
        .upsert(
          { keyword, display_name: keyword, storefront: 'us', is_watched: true },
          { onConflict: 'keyword' },
        )
      await db.from('niche_candidates').update({ status: 'watched' }).eq('keyword', keyword)
    } else {
      await db.from('niches').update({ is_watched: false }).eq('keyword', keyword)
      await db.from('niche_candidates').update({ status: 'validated' }).eq('keyword', keyword)
    }

    return json({ ok: true, keyword, action })
  } catch (e) {
    return json({ error: String(e) }, 500)
  }
})

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, 'Content-Type': 'application/json' },
  })
}
