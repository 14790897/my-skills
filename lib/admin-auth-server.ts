import { jwtVerify } from 'jose';

const SECRET = new TextEncoder().encode(
  process.env.ADMIN_JWT_SECRET || 'dev-only-secret-change-in-production'
);

export async function verifyAdminServer(token: string): Promise<boolean> {
  try {
    await jwtVerify(token, SECRET);
    return true;
  } catch {
    return false;
  }
}
