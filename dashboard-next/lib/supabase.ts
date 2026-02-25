import postgres from "postgres";

const connectionString = process.env.SUPABASE_DB_URL!;

export const sql = postgres(connectionString, {
  ssl: { rejectUnauthorized: false },
  max: 5,
  idle_timeout: 20,
  connect_timeout: 5,
  prepare: false, // Supabase Supavisor 호환 + serverless 환경 안정성
});
