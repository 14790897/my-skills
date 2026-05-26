import { NextRequest, NextResponse } from 'next/server';
import { jwtVerify } from 'jose';

const SECRET = new TextEncoder().encode(
  process.env.ADMIN_JWT_SECRET || 'dev-only-secret-change-in-production'
);

// Verify admin token from cookie
export async function verifyAdmin(req: NextRequest): Promise<boolean> {
  const token = req.cookies.get('admin_token')?.value;
  if (!token) return false;
  try {
    await jwtVerify(token, SECRET);
    return true;
  } catch {
    return false;
  }
}

// Unauthorized response
export function unauthorized(): NextResponse {
  const res = NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  res.cookies.delete('admin_token');
  return res;
}
