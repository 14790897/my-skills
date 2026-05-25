'use client';

import { useState, useCallback } from 'react';
import type { SkillMeta } from '@/lib/skills';
import SearchBar from './search-bar';
import SkillCard from './skill-card';

interface SkillListProps {
  skills: SkillMeta[];
}

export default function SkillList({ skills }: SkillListProps) {
  const [query, setQuery] = useState('');
  const [searchValue, setSearchValue] = useState('');

  const handleSearch = useCallback((q: string) => {
    setSearchValue(q);
  }, []);

  const filtered = searchValue
    ? skills.filter(
        (s) =>
          s.name.toLowerCase().includes(searchValue.toLowerCase()) ||
          s.description.toLowerCase().includes(searchValue.toLowerCase())
      )
    : skills;

  return (
    <>
      <SearchBar onSearch={handleSearch} />
      {filtered.length === 0 ? (
        <p className="text-[#555] text-sm py-6">No skills found.</p>
      ) : (
        filtered.map((skill) => (
          <SkillCard key={skill.name} skill={skill} highlight={searchValue} />
        ))
      )}
    </>
  );
}
