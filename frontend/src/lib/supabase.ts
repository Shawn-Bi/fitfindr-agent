import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// The browser uses Supabase for sign-in only. Every data request goes through
// the FitFindr API with the user's access token (DECISIONS.md #13).
let client: SupabaseClient | null = null;

export function supabase(): SupabaseClient {
  if (!client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !anon) {
      throw new Error("NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set.");
    }
    client = createClient(url, anon, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    });
  }
  return client;
}
