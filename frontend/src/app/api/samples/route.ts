import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

/**
 * API Route: GET /api/samples
 *
 * Fetches pulse oximetry samples from a CSV file.
 *
 * Query Parameters:
 * - path: Path to CSV file (relative to workspace root or absolute)
 * - maxRows: Maximum number of rows to return (default: 120)
 * - onlyPlausible: Filter to plausible samples only (default: true)
 *
 * Response:
 * - 200: JSON array of sample objects
 * - 400: Bad request (missing/invalid parameters)
 * - 404: File not found
 * - 500: Server error
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  try {
    const searchParams = request.nextUrl.searchParams;
    const csvPath = searchParams.get('path') ?? '../validated_60s.csv';
    const maxRows = parseInt(searchParams.get('maxRows') ?? '120', 10);
    const onlyPlausible = searchParams.get('onlyPlausible') !== 'false';

    // Resolve path relative to frontend directory
    const resolvedPath = path.isAbsolute(csvPath)
      ? csvPath
      : path.resolve(process.cwd(), '..', csvPath);

    // Security check: ensure path is within workspace
    const workspaceRoot = path.resolve(process.cwd(), '..');
    if (!resolvedPath.startsWith(workspaceRoot)) {
      return NextResponse.json(
        { error: 'Access denied: path outside workspace' },
        { status: 403 }
      );
    }

    // Check file exists
    try {
      await fs.access(resolvedPath);
    } catch {
      return NextResponse.json(
        { error: `File not found: ${csvPath}` },
        { status: 404 }
      );
    }

    // Read and parse CSV
    const csvContent = await fs.readFile(resolvedPath, 'utf-8');
    const lines = csvContent.trim().split('\n');

    if (lines.length < 2) {
      return NextResponse.json(
        { error: 'CSV file is empty or has no data rows' },
        { status: 400 }
      );
    }

    const headers = lines[0].split(',');
    const samples: Array<Record<string, string | number | boolean>> = [];

    // Parse data rows (newest last)
    const dataLines = lines.slice(1);
    const startIndex = Math.max(0, dataLines.length - maxRows);

    for (let i = startIndex; i < dataLines.length; i++) {
      const values = dataLines[i].split(',');
      const row: Record<string, string | number | boolean> = {};

      headers.forEach((header, index) => {
        const value = values[index]?.trim() ?? '';
        const headerTrimmed = header.trim();

        // Type conversion based on field name
        if (['elapsed_s', 'perfusion_index'].includes(headerTrimmed)) {
          row[headerTrimmed] = parseFloat(value) || 0;
        } else if (['spo2_percent', 'pulse_bpm'].includes(headerTrimmed)) {
          row[headerTrimmed] = parseInt(value, 10) || 0;
        } else if (headerTrimmed === 'plausible') {
          row[headerTrimmed] = value === '1';
        } else {
          row[headerTrimmed] = value;
        }
      });

      // Filter by plausible if requested
      if (onlyPlausible && !row.plausible) {
        continue;
      }

      samples.push(row);
    }

    return NextResponse.json({
      samples,
      metadata: {
        totalRows: dataLines.length,
        returnedRows: samples.length,
        filePath: csvPath,
        timestamp: new Date().toISOString(),
      },
    });
  } catch (error) {
    console.error('Error reading CSV:', error);
    return NextResponse.json(
      {
        error: 'Failed to read CSV file',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
