/**
 * Direct PostgreSQL Database Client
 * Bypasses MCP for more reliable database access
 */

import { Pool, QueryResult } from 'pg';

// Database connection configuration
const DB_CONFIG = {
  host: process.env.POSTGRES_HOST || 'localhost',
  port: parseInt(process.env.POSTGRES_PORT || '5432'),
  database: process.env.POSTGRES_DATABASE || 'topmate',
  user: process.env.POSTGRES_USER || 'postgres',
  password: process.env.POSTGRES_PASSWORD || '',
  ssl: process.env.POSTGRES_SSL === 'true' ? { rejectUnauthorized: false } : false,
  max: 20, // Maximum number of clients in the pool
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 10000,
};

let pool: Pool | null = null;

/**
 * Get or create database connection pool
 */
export function getPool(): Pool {
  if (!pool) {
    pool = new Pool(DB_CONFIG);

    pool.on('error', (err) => {
      console.error('[DB] Unexpected pool error:', err);
    });

    console.log('[DB] Connection pool created');
  }

  return pool;
}

/**
 * Execute a read-only SQL query
 */
export async function executeQuery(sql: string, params: any[] = []): Promise<any[]> {
  // Validate read-only
  validateReadOnlyQuery(sql);

  const pool = getPool();
  const client = await pool.connect();

  try {
    console.log('[DB] Executing query:', sql.substring(0, 100) + '...');
    const result: QueryResult = await client.query(sql, params);
    console.log('[DB] Query returned', result.rows.length, 'rows');
    return result.rows;
  } catch (error: any) {
    console.error('[DB] Query failed:', error.message);
    throw new Error(`Database query failed: ${error.message}`);
  } finally {
    client.release();
  }
}

/**
 * Get all table names from the database
 */
export async function getAllTables(): Promise<string[]> {
  const query = `
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE'
    ORDER BY table_name
  `;

  const rows = await executeQuery(query);
  return rows.map(row => row.table_name);
}

/**
 * Get columns for a specific table
 */
export async function getTableColumns(tableName: string): Promise<Array<{ name: string; type: string }>> {
  const query = `
    SELECT
      column_name as name,
      data_type as type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = $1
    ORDER BY ordinal_position
  `;

  const rows = await executeQuery(query, [tableName]);
  return rows;
}

/**
 * Get database schema (tables and columns)
 */
export async function getDatabaseSchema(): Promise<Array<{ table: string; columns: Array<{ name: string; type: string }> }>> {
  const tables = await getAllTables();
  const schema = [];

  for (const table of tables) {
    try {
      const columns = await getTableColumns(table);
      schema.push({ table, columns });
    } catch (error: any) {
      console.warn(`[DB] Failed to get columns for ${table}:`, error.message);
    }
  }

  return schema;
}

/**
 * Analyze prompt and suggest relevant queries
 */
export async function analyzePromptAndSuggestQueries(
  prompt: string,
  schema: Array<{ table: string; columns: Array<{ name: string; type: string }> }>
): Promise<Array<{ table: string; query: string; reasoning: string }>> {
  const suggestions = [];

  // Extract person name from prompt (simple pattern matching)
  const nameMatch = prompt.match(/from\s+(\w+)/i) || prompt.match(/by\s+(\w+)/i);
  const personName = nameMatch ? nameMatch[1] : null;

  // Check for specific intent
  const isTestimonial = /testimonial|review|feedback|comment/i.test(prompt);
  const isService = /service|offering|product/i.test(prompt);
  const isBooking = /booking|appointment|reservation/i.test(prompt);
  const isAnalytics = /total|count|stat|analytic|number|metric/i.test(prompt);

  // Search for relevant tables
  for (const { table, columns } of schema) {
    const tableLower = table.toLowerCase();
    const columnNames = columns.map(c => c.name.toLowerCase());

    // Testimonials/Reviews
    if (isTestimonial && (tableLower.includes('testimonial') || tableLower.includes('review') || tableLower.includes('feedback'))) {
      let query = `SELECT * FROM ${table}`;
      const whereConditions = [];

      // Add name filter if provided
      if (personName) {
        const nameColumns = columnNames.filter(c =>
          c.includes('name') || c.includes('reviewer') || c.includes('author') || c.includes('follower')
        );

        if (nameColumns.length > 0) {
          const nameFilters = nameColumns.map(col => `${col} ILIKE '%${personName}%'`).join(' OR ');
          whereConditions.push(`(${nameFilters})`);
        }
      }

      // Add WHERE clause if we have conditions
      if (whereConditions.length > 0) {
        query += ` WHERE ${whereConditions.join(' AND ')}`;
      }

      // Add ordering and limit
      if (columnNames.includes('created') || columnNames.includes('created_at')) {
        query += ` ORDER BY ${columnNames.includes('created') ? 'created' : 'created_at'} DESC`;
      }
      query += ` LIMIT 20`;

      suggestions.push({
        table,
        query,
        reasoning: `Contains testimonials/reviews${personName ? ` filtered by name "${personName}"` : ''}`
      });
    }

    // Services
    if (isService && tableLower.includes('service')) {
      let query = `SELECT * FROM ${table}`;

      if (columnNames.includes('created_at')) {
        query += ` ORDER BY created_at DESC`;
      }
      query += ` LIMIT 20`;

      suggestions.push({
        table,
        query,
        reasoning: 'Contains service information'
      });
    }

    // Bookings with analytics
    if (isBooking && tableLower.includes('booking')) {
      if (isAnalytics) {
        // Aggregated query for analytics
        const query = `
          SELECT
            COUNT(*) as total_bookings,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled
          FROM ${table}
        `;
        suggestions.push({
          table,
          query: query.trim(),
          reasoning: 'Booking statistics and counts'
        });
      } else {
        // Individual bookings
        let query = `SELECT * FROM ${table}`;
        if (columnNames.includes('created_at')) {
          query += ` ORDER BY created_at DESC`;
        }
        query += ` LIMIT 20`;

        suggestions.push({
          table,
          query,
          reasoning: 'Contains booking information'
        });
      }
    }
  }

  return suggestions;
}

/**
 * Validate read-only query
 */
function validateReadOnlyQuery(sql: string): void {
  const normalized = sql.toLowerCase().trim();

  const dangerousKeywords = [
    'insert', 'update', 'delete', 'drop', 'alter', 'truncate',
    'create table', 'create index', 'grant', 'revoke'
  ];

  for (const keyword of dangerousKeywords) {
    const regex = new RegExp(`\\b${keyword.replace(/\s+/g, '\\s+')}\\b`, 'i');
    if (regex.test(sql)) {
      throw new Error(`READ-ONLY MODE: Query cannot contain '${keyword}' operation`);
    }
  }

  if (!normalized.startsWith('select') && !normalized.startsWith('with')) {
    throw new Error('READ-ONLY MODE: Only SELECT queries are allowed');
  }
}

/**
 * Close the database pool
 */
export async function closePool(): Promise<void> {
  if (pool) {
    await pool.end();
    pool = null;
    console.log('[DB] Connection pool closed');
  }
}
