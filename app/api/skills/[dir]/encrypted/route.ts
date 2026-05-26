import { NextResponse } from 'next/server';
import { readFileSync, existsSync } from 'fs';
import { resolve } from 'path';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ dir: string }> }
) {
  const { dir } = await params;

  // Security: prevent path traversal
  if (dir.includes('..') || dir.includes('/') || dir.includes('\\')) {
    return NextResponse.json({ error: 'Invalid directory name' }, { status: 400 });
  }

  const datPath = resolve(process.cwd(), 'public', 'encrypted', `${dir}.dat`);

  if (!existsSync(datPath)) {
    return NextResponse.json(
      { error: 'Encrypted skill not found or not encrypted' },
      { status: 404 }
    );
  }

  const raw = readFileSync(datPath);
  const b64 = raw.toString('base64');

  return NextResponse.json({ encrypted: true, data: b64 });
}
