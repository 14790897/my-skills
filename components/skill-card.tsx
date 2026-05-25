import Link from 'next/link';
import type { SkillMeta } from '@/lib/skills';

interface SkillCardProps {
  skill: SkillMeta;
  highlight?: string;
}

function highlightText(text: string, query: string): React.ReactNode {
  if (!query) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'));
  return parts.map((part, i) =>
    part.toLowerCase() === query.toLowerCase() ? (
      <span key={i} className="text-[#e0e0e0] bg-[#222] rounded-sm px-0.5">
        {part}
      </span>
    ) : (
      part
    )
  );
}

export default function SkillCard({ skill, highlight }: SkillCardProps) {
  const dirName = skill.url.replace(/^\/(.+)\/SKILL\.md$/, '$1');

  return (
    <Link
      href={`/${dirName}`}
      className="block border border-[#1a1a1a] rounded-lg p-5 mb-3 transition-colors hover:border-[#333] group"
    >
      <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
        <span className="text-[1.1rem] font-semibold text-white font-mono">
          {highlight ? highlightText(skill.name, highlight) : skill.name}
        </span>
        <span className="text-xs text-[#555] font-mono transition-colors group-hover:text-[#999]">
          {skill.url}
        </span>
      </div>
      <p className="text-sm text-[#888] leading-relaxed">
        {highlight ? highlightText(skill.description, highlight) : skill.description}
      </p>
    </Link>
  );
}
