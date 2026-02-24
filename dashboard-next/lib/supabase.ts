import postgres from "postgres";

const connectionString = process.env.SUPABASE_DB_URL!;

export const sql = postgres(connectionString, {
  ssl: { rejectUnauthorized: false },
  max: 10,
  idle_timeout: 30,
  connect_timeout: 10,
  prepare: true,
});
