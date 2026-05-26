import type { Metadata } from 'next';
import '../globals.css';

export const metadata: Metadata = {
  title: 'Admin - My Skills',
  description: 'Skill management',
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="min-h-screen bg-[#0a0a0a] text-[#e0e0e0]">{children}</div>;
}
