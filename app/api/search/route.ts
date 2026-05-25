import { NextRequest, NextResponse } from 'next/server';
import { searchSkills } from '@/lib/skills';

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get('q');

  if (!q || !q.trim()) {
    return NextResponse.json({ error: 'Missing query parameter: q' }, { status: 400 });
  }

  const results = searchSkills(q);

  return NextResponse.json({
    query: q.trim(),
    count: results.length,
    results,
  }, {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}
