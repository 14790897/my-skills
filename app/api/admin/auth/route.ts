import { NextRequest, NextResponse } from 'next/server';
import { SignJWT } from 'jose';

const SECRET = new TextEncoder().encode(
  process.env.ADMIN_JWT_SECRET || 'dev-only-secret-change-in-production'
);

export async function POST(req: NextRequest) {
  const { password } = await req.json();

  if (password !== process.env.ADMIN_PASSWORD) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const token = await new SignJWT({ role: 'admin' })
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime('1d')
    .sign(SECRET);

  const res = NextResponse.json({ ok: true });
  res.cookies.set('admin_token', token, {
    httpOnly: true,
    sameSite: 'lax',
    maxAge: 86400,
    path: '/',
  });
  return res;
}
