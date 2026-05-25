import { getAllSkills } from '@/lib/skills';
import SkillList from '@/components/skill-list';
import Link from 'next/link';

export default function HomePage() {
  const skills = getAllSkills();

  return (
    <main className="max-w-[720px] mx-auto px-6 py-12">
      <h1 className="text-2xl font-semibold mb-1 flex items-center gap-2.5">
        My Skills
      </h1>
      <p className="text-[#888] text-sm mb-6">WorkBuddy skill registry</p>

      {/* API hint */}
      <div className="bg-[#0d0d0d] border border-[#1a1a1a] rounded-md py-2.5 px-3.5 mb-8 font-mono text-xs text-[#555] break-all">
        <span className="text-[#888]">AI search:&nbsp;</span>
        <Link href="/api/search?q=your+query" className="hover:text-[#888] transition-colors">
          /api/search?q=your+query
        </Link>
      </div>

      <SkillList skills={skills} />

      {/* Footer */}
      <footer className="mt-12 pt-6 border-t border-[#1a1a1a] text-[#444] text-xs flex justify-between flex-wrap gap-2">
        <Link href="/index.json" className="text-[#555] hover:text-[#888] transition-colors">
          index.json
        </Link>
        <span>Powered by Vercel</span>
      </footer>
    </main>
  );
}
