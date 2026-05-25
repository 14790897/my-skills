'use client';

import { useState, useEffect, useRef } from 'react';

interface SearchBarProps {
  onSearch: (query: string) => void;
}

export default function SearchBar({ onSearch }: SearchBarProps) {
  const [value, setValue] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onSearch(value.trim());
    }, 150);
    return () => clearTimeout(debounceRef.current);
  }, [value, onSearch]);

  return (
    <div className="relative mb-8">
      <svg
        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#555]"
        width="16"
        height="16"
        viewBox="0 0 16 16"
        fill="none"
      >
        <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search skills..."
        autoComplete="off"
        className="w-full py-3 pl-10 pr-4 bg-[#111] border border-[#222] rounded-lg text-[#e0e0e0] text-[0.95rem] outline-none transition-colors focus:border-[#444] placeholder:text-[#555]"
      />
    </div>
  );
}
