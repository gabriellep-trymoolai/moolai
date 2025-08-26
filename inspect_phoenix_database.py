#!/usr/bin/env python3
"""Comprehensive Phoenix database inspection script."""

import psycopg2
import json
from datetime import datetime
import os
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', 5432),
    'database': os.getenv('DB_NAME', 'orchestrator_org_001'),
    'user': os.getenv('DB_USER', 'orchestrator_user'),
    'password': os.getenv('DB_PASSWORD', 'orchestrator_pass')
}

def inspect_phoenix_schema():
    """Inspect Phoenix schema structure."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("PHOENIX DATABASE STRUCTURE")
    print("=" * 100)
    
    # List all Phoenix tables with row counts
    cur.execute("""
        SELECT 
            t.table_name,
            pg_size_pretty(pg_total_relation_size('"phoenix"."' || t.table_name || '"')) as size,
            (SELECT COUNT(*) FROM phoenix.%s) as row_count,
            obj_description(c.oid, 'pg_class') as description
        FROM information_schema.tables t
        LEFT JOIN pg_class c ON c.relname = t.table_name AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'phoenix')
        WHERE t.table_schema = 'phoenix'
        ORDER BY pg_total_relation_size('"phoenix"."' || t.table_name || '"') DESC
        LIMIT 10
    """ % ('spans'))  # Simplified for main table
    
    # Get actual counts for each table
    tables_info = []
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'phoenix'
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    
    for table in tables:
        table_name = table[0]
        try:
            cur.execute(f"SELECT COUNT(*) FROM phoenix.{table_name}")
            count = cur.fetchone()[0]
            
            cur.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size('"phoenix"."{table_name}"'))
            """)
            size = cur.fetchone()[0]
            
            tables_info.append([table_name, count, size])
        except:
            tables_info.append([table_name, 'N/A', 'N/A'])
    
    print("\n📊 Phoenix Tables Overview:")
    print(tabulate(tables_info, headers=['Table', 'Row Count', 'Size'], tablefmt='grid'))
    
    cur.close()
    conn.close()

def inspect_spans_table():
    """Detailed inspection of spans table structure and sample data."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("PHOENIX SPANS TABLE STRUCTURE")
    print("=" * 100)
    
    # Get column information
    cur.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'phoenix' AND table_name = 'spans'
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    
    print("\n📋 Spans Table Columns:")
    print(tabulate(columns, headers=['Column', 'Type', 'Max Length', 'Nullable'], tablefmt='grid'))
    
    # Get sample span data
    print("\n" + "=" * 100)
    print("SAMPLE SPAN DATA (Most Recent)")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            id,
            trace_id,
            span_id,
            parent_id,
            name,
            span_kind,
            start_time,
            end_time,
            EXTRACT(EPOCH FROM (end_time - start_time)) * 1000 as duration_ms,
            status_code,
            status_message,
            jsonb_pretty(attributes) as attributes_pretty
        FROM phoenix.spans
        ORDER BY start_time DESC
        LIMIT 3
    """)
    
    spans = cur.fetchall()
    
    for i, span in enumerate(spans, 1):
        print(f"\n{'='*50} SPAN {i} {'='*50}")
        print(f"ID:           {span[0]}")
        print(f"Trace ID:     {span[1]}")
        print(f"Span ID:      {span[2]}")
        print(f"Parent ID:    {span[3] or 'None (Root Span)'}")
        print(f"Name:         {span[4]}")
        print(f"Span Kind:    {span[5]}")
        print(f"Start Time:   {span[6]}")
        print(f"End Time:     {span[7]}")
        print(f"Duration:     {span[8]:.2f}ms" if span[8] else "N/A")
        print(f"Status:       {span[9]} - {span[10] or 'OK'}")
        print(f"\n📦 Attributes (JSON):")
        if span[11]:
            # Truncate if too long
            attr_str = span[11]
            if len(attr_str) > 2000:
                attr_str = attr_str[:2000] + "\n... (truncated)"
            print(attr_str)
    
    cur.close()
    conn.close()

def analyze_llm_spans():
    """Analyze LLM-specific spans and their attributes."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("LLM SPANS ANALYSIS")
    print("=" * 100)
    
    # Analyze span names
    cur.execute("""
        SELECT 
            name,
            COUNT(*) as count,
            AVG(EXTRACT(EPOCH FROM (end_time - start_time)) * 1000) as avg_duration_ms
        FROM phoenix.spans
        WHERE start_time > NOW() - INTERVAL '7 days'
        GROUP BY name
        ORDER BY count DESC
        LIMIT 10
    """)
    
    name_stats = cur.fetchall()
    print("\n📊 Top Span Names (Last 7 Days):")
    print(tabulate(name_stats, headers=['Name', 'Count', 'Avg Duration (ms)'], tablefmt='grid'))
    
    # Check for UNKNOWN spans
    cur.execute("""
        SELECT COUNT(*) 
        FROM phoenix.spans 
        WHERE name = 'UNKNOWN' OR name IS NULL OR name = ''
    """)
    unknown_count = cur.fetchone()[0]
    print(f"\n⚠️  UNKNOWN/Empty Spans: {unknown_count}")
    
    # Analyze LLM attributes presence
    print("\n" + "=" * 100)
    print("LLM ATTRIBUTES ANALYSIS")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE attributes ? 'gen_ai') as has_gen_ai,
            COUNT(*) FILTER (WHERE attributes->'gen_ai' ? 'system') as has_gen_ai_system,
            COUNT(*) FILTER (WHERE attributes->'gen_ai'->'request' ? 'model') as has_model,
            COUNT(*) FILTER (WHERE attributes->'gen_ai'->'usage' ? 'prompt_tokens') as has_prompt_tokens,
            COUNT(*) FILTER (WHERE attributes->'gen_ai'->'usage' ? 'completion_tokens') as has_completion_tokens,
            COUNT(*) FILTER (WHERE attributes ? 'llm.system') as has_llm_system,
            COUNT(*) FILTER (WHERE attributes ? 'phoenix.span_type') as has_phoenix_type,
            COUNT(*) as total_spans
        FROM phoenix.spans
        WHERE start_time > NOW() - INTERVAL '24 hours'
    """)
    
    attr_stats = cur.fetchone()
    
    if attr_stats[7] > 0:
        print("\n📊 Attribute Presence (Last 24 Hours):")
        stats_data = [
            ['gen_ai namespace', attr_stats[0], f"{attr_stats[0]*100//attr_stats[7]}%"],
            ['gen_ai.system', attr_stats[1], f"{attr_stats[1]*100//attr_stats[7]}%"],
            ['gen_ai.request.model', attr_stats[2], f"{attr_stats[2]*100//attr_stats[7]}%"],
            ['gen_ai.usage.prompt_tokens', attr_stats[3], f"{attr_stats[3]*100//attr_stats[7]}%"],
            ['gen_ai.usage.completion_tokens', attr_stats[4], f"{attr_stats[4]*100//attr_stats[7]}%"],
            ['llm.system (custom)', attr_stats[5], f"{attr_stats[5]*100//attr_stats[7]}%"],
            ['phoenix.span_type (custom)', attr_stats[6], f"{attr_stats[6]*100//attr_stats[7]}%"],
            ['TOTAL SPANS', attr_stats[7], '100%']
        ]
        print(tabulate(stats_data, headers=['Attribute', 'Count', 'Percentage'], tablefmt='grid'))
    
    # Show sample LLM span attributes
    print("\n" + "=" * 100)
    print("SAMPLE LLM SPAN ATTRIBUTES")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            name,
            attributes->'gen_ai'->>'system' as llm_system,
            attributes->'gen_ai'->'request'->>'model' as model,
            attributes->'gen_ai'->'usage'->>'prompt_tokens' as prompt_tokens,
            attributes->'gen_ai'->'usage'->>'completion_tokens' as completion_tokens,
            attributes->>'llm.system' as custom_llm_system,
            attributes->>'phoenix.span_type' as phoenix_type,
            attributes->>'span.kind' as span_kind_attr
        FROM phoenix.spans
        WHERE attributes ? 'gen_ai' OR attributes ? 'llm.system'
        ORDER BY start_time DESC
        LIMIT 5
    """)
    
    llm_spans = cur.fetchall()
    
    if llm_spans:
        headers = ['Name', 'LLM System', 'Model', 'Prompt Tokens', 'Completion Tokens', 'Custom System', 'Phoenix Type', 'Span Kind']
        print(tabulate(llm_spans, headers=headers, tablefmt='grid'))
    else:
        print("❌ No LLM spans found with gen_ai or llm.system attributes")
    
    cur.close()
    conn.close()

def analyze_span_costs():
    """Analyze span costs data."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("SPAN COSTS ANALYSIS")
    print("=" * 100)
    
    # Check span_costs table
    cur.execute("""
        SELECT 
            COUNT(*) as total_cost_records,
            SUM(total_cost) as total_cost_sum,
            AVG(total_cost) as avg_cost,
            MIN(total_cost) as min_cost,
            MAX(total_cost) as max_cost
        FROM phoenix.span_costs
    """)
    
    cost_stats = cur.fetchone()
    
    if cost_stats[0] > 0:
        print(f"\n💰 Cost Statistics:")
        print(f"   Total Records: {cost_stats[0]}")
        print(f"   Total Cost: ${cost_stats[1] or 0:.6f}")
        print(f"   Average Cost: ${cost_stats[2] or 0:.6f}")
        print(f"   Min Cost: ${cost_stats[3] or 0:.6f}")
        print(f"   Max Cost: ${cost_stats[4] or 0:.6f}")
    else:
        print("\n❌ No cost data found in span_costs table")
    
    # Sample cost records
    cur.execute("""
        SELECT 
            sc.span_rowid,
            s.name,
            sc.total_cost,
            sc.prompt_token_cost,
            sc.completion_token_cost,
            s.attributes->'gen_ai'->'request'->>'model' as model
        FROM phoenix.span_costs sc
        JOIN phoenix.spans s ON s.id = sc.span_rowid
        ORDER BY sc.total_cost DESC
        LIMIT 5
    """)
    
    cost_records = cur.fetchall()
    
    if cost_records:
        print("\n📊 Top 5 Most Expensive Spans:")
        headers = ['Span ID', 'Name', 'Total Cost', 'Prompt Cost', 'Completion Cost', 'Model']
        print(tabulate(cost_records, headers=headers, tablefmt='grid', floatfmt=".6f"))
    
    cur.close()
    conn.close()

def test_analytics_query():
    """Test the exact analytics query used by the dashboard."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("TESTING ANALYTICS QUERY")
    print("=" * 100)
    
    # Test the fixed query
    query = """
        WITH llm_spans AS (
            SELECT 
                s.*,
                (s.attributes->'gen_ai'->'usage'->>'prompt_tokens')::INTEGER as prompt_tokens,
                (s.attributes->'gen_ai'->'usage'->>'completion_tokens')::INTEGER as completion_tokens,
                (s.attributes->'gen_ai'->'usage'->>'prompt_tokens')::INTEGER + 
                (s.attributes->'gen_ai'->'usage'->>'completion_tokens')::INTEGER as total_tokens,
                s.attributes->'gen_ai'->'request'->>'model' as model_name,
                s.attributes->'gen_ai'->>'system' as provider,
                EXTRACT(EPOCH FROM (s.end_time - s.start_time)) * 1000 as duration_ms,
                COALESCE(sc.total_cost, 0) as cost
            FROM phoenix.spans s
            LEFT JOIN phoenix.span_costs sc ON s.id = sc.span_rowid
            WHERE (
                s.name ILIKE '%openai%' OR 
                s.name ILIKE '%chat%' OR 
                s.attributes ? 'gen_ai' OR 
                s.span_kind = 'LLM' OR
                (s.name = 'UNKNOWN' AND s.attributes ? 'gen_ai') OR
                s.attributes ? 'llm.system' OR
                s.attributes ? 'phoenix.span_type'
            )
            AND s.start_time >= NOW() - INTERVAL '30 days'
        )
        SELECT 
            COUNT(*) as matching_spans,
            COUNT(*) FILTER (WHERE prompt_tokens > 0 OR completion_tokens > 0) as spans_with_tokens,
            SUM(COALESCE(total_tokens, 0)) as total_tokens,
            SUM(cost) as total_cost,
            AVG(duration_ms) as avg_duration_ms
        FROM llm_spans
    """
    
    cur.execute(query)
    result = cur.fetchone()
    
    print(f"\n📊 Analytics Query Results (Last 30 Days):")
    print(f"   Matching Spans: {result[0]}")
    print(f"   Spans with Tokens: {result[1]}")
    print(f"   Total Tokens: {result[2]}")
    print(f"   Total Cost: ${result[3] or 0:.6f}")
    print(f"   Avg Duration: {result[4] or 0:.2f}ms")
    
    if result[0] == 0:
        print("\n❌ PROBLEM: No spans match the analytics query criteria!")
        print("   This means the dashboard will show zeros.")
    elif result[1] == 0:
        print("\n⚠️  WARNING: Spans found but none have token data!")
        print("   Token counting may not be working properly.")
    
    cur.close()
    conn.close()

def main():
    """Run all Phoenix database inspections."""
    print("\n" + "🔍 PHOENIX DATABASE INSPECTION" + "\n")
    print(f"Database: {DB_CONFIG['database']}")
    print(f"Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    
    try:
        # Run all inspections
        inspect_phoenix_schema()
        inspect_spans_table()
        analyze_llm_spans()
        analyze_span_costs()
        test_analytics_query()
        
        print("\n" + "=" * 100)
        print("INSPECTION COMPLETE")
        print("=" * 100)
        print("\n📝 Key Findings:")
        print("1. Check if spans have 'UNKNOWN' names - indicates classification issue")
        print("2. Check if gen_ai attributes are present - indicates OpenTelemetry instrumentation working")
        print("3. Check if llm.system/phoenix.span_type present - indicates custom processor working")
        print("4. Check if analytics query returns data - indicates dashboard should work")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()