import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { verifyAdminServer } from '@/lib/admin-auth-server';
import SkillEditor from '@/components/skill-editor';

export default async function SkillEditPage({
  params,
}: {
  params: Promise<{ dir: string }>;
}) {
  const { dir } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get('admin_token')?.value;

  if (!token || !(await verifyAdminServer(token))) {
    redirect('/admin');
  }

  // Fetch skill content from API
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';
  const res = await fetch(`${baseUrl}/api/admin/skills/${dir}`, {
    headers: { Cookie: `admin_token=${token}` },
    cache: 'no-store',
  });

  if (!res.ok) {
    throw new Error('Failed to load skill');
  }

  const { raw, frontmatter, body } = await res.json();

  return (
    <SkillEditor
      dir={dir}
      initialRaw={raw}
      initialFrontmatter={frontmatter}
      initialBody={body}
    />
  );
}
