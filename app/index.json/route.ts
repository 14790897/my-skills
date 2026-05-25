import { NextResponse } from 'next/server';
import { getAllSkills } from '@/lib/skills';

export async function GET() {
  const skills = getAllSkills();
  return NextResponse.json(skills, {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

export const dynamic = 'force-static';
