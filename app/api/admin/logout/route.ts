import { NextRequest, NextResponse } from 'next/server';

export async function POST(_req: NextRequest) {
  const res = NextResponse.json({ ok: true });
  res.cookies.delete('admin_token');
  return res;
}
