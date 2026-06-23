// Calls the `watch` Edge Function (service-role write) to add/remove a niche from the
// watch list. The SPA can't write directly (anon key is read-only via RLS), so the
// button routes through the function. The anon key authorizes the call.

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export async function setWatch(keyword: string, action: 'add' | 'remove'): Promise<void> {
  const res = await fetch(`${url}/functions/v1/watch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      apikey: anonKey,
      Authorization: `Bearer ${anonKey}`,
    },
    body: JSON.stringify({ keyword, action }),
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`watch ${action} failed (${res.status}): ${body}`)
  }
}
