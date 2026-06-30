import { createClient as createSupabaseClient } from '@supabase/supabase-js'
import type { Database } from './database.types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SupabaseClient = ReturnType<typeof createAdminClient>
export type SupabaseAnonClient = ReturnType<typeof createAnonClient>

// ---------------------------------------------------------------------------
// Validation helper
// ---------------------------------------------------------------------------

function requireEnv(name: string): string {
  const value = process.env[name]
  if (!value) {
    throw new Error(
      `[acm/database] Missing required environment variable: ${name}. ` +
        `Copy .env.example to .env and fill in your Supabase credentials.`
    )
  }
  return value
}

// ---------------------------------------------------------------------------
// Admin client  (service-role key — server-side only, bypasses RLS)
// ---------------------------------------------------------------------------

let _adminClient: SupabaseClient | null = null

/**
 * Returns a singleton Supabase client authenticated with the service-role key.
 * Use for server-side operations that need to bypass RLS (e.g. agent workers,
 * cron jobs, migrations).
 *
 * NEVER expose this client or its key to the browser.
 */
export function createAdminClient(
  supabaseUrl = requireEnv('SUPABASE_URL'),
  serviceRoleKey = requireEnv('SUPABASE_SERVICE_ROLE_KEY')
): ReturnType<typeof createSupabaseClient<Database>> {
  if (_adminClient) return _adminClient

  _adminClient = createSupabaseClient<Database>(supabaseUrl, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
    db: {
      schema: 'public',
    },
  })

  return _adminClient
}

// ---------------------------------------------------------------------------
// Anon client  (anon key — safe for server components, respects RLS)
// ---------------------------------------------------------------------------

let _anonClient: SupabaseAnonClient | null = null

/**
 * Returns a singleton Supabase client authenticated with the anon key.
 * Respects Row Level Security — safe to use in API routes and server actions.
 * For browser / Next.js App Router, use @supabase/ssr instead.
 */
export function createAnonClient(
  supabaseUrl = requireEnv('SUPABASE_URL'),
  anonKey = requireEnv('SUPABASE_ANON_KEY')
): ReturnType<typeof createSupabaseClient<Database>> {
  if (_anonClient) return _anonClient

  _anonClient = createSupabaseClient<Database>(supabaseUrl, anonKey, {
    auth: {
      autoRefreshToken: true,
      persistSession: true,
    },
    db: {
      schema: 'public',
    },
  })

  return _anonClient
}

// ---------------------------------------------------------------------------
// Convenience re-export — default is the anon client (safest default)
// ---------------------------------------------------------------------------

export const createClient = createAnonClient

// ---------------------------------------------------------------------------
// Query helpers
// ---------------------------------------------------------------------------

/**
 * Typed helper: fetch a single row or null without throwing on PGRST116.
 *
 * @example
 * const campaign = await findOne(
 *   db.from('campaigns').select('*').eq('id', id)
 * )
 */
export async function findOne<T>(
  query: PromiseLike<{ data: T | null; error: { message: string; code: string } | null }>
): Promise<T | null> {
  const { data, error } = await query
  if (error && error.code !== 'PGRST116') {
    throw new Error(`[acm/database] Supabase query error: ${error.message}`)
  }
  return data
}

/**
 * Typed helper: fetch multiple rows and throw on error.
 */
export async function findMany<T>(
  query: PromiseLike<{ data: T[] | null; error: { message: string } | null }>
): Promise<T[]> {
  const { data, error } = await query
  if (error) throw new Error(`[acm/database] Supabase query error: ${error.message}`)
  return data ?? []
}

/**
 * Typed helper: insert a row and return it, throwing on error.
 */
export async function insertOne<T>(
  query: PromiseLike<{ data: T | null; error: { message: string } | null }>
): Promise<T> {
  const { data, error } = await query
  if (error) throw new Error(`[acm/database] Supabase insert error: ${error.message}`)
  if (!data) throw new Error('[acm/database] Insert returned no data')
  return data
}
