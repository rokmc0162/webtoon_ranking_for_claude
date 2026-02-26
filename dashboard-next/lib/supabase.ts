import postgres from "postgres";

const connectionString = process.env.SUPABASE_DB_URL!;

export const sql = postgres(connectionString, {
  ssl: { rejectUnauthorized: false },
  max: 20,
  idle_timeout: 30,
  connect_timeout: 10,
  prepare: false, // Supabase Supavisor 호환 + serverless 환경 안정성
});
