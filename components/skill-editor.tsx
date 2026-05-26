'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Cookies from 'js-cookie';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
  dir: string;
  initialRaw: string;
  initialFrontmatter: Record<string, unknown>;
  initialBody: string;
}

export default function SkillEditor({ dir, initialRaw, initialFrontmatter, initialBody }: Props) {
  const [raw, setRaw] = useState(initialRaw);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState<'ok' | 'err'>('ok');
  const router = useRouter();

  async function handleSave() {
    setSaving(true);
    setMessage('');

    try {
      const res = await fetch(`/api/admin/skills/${dir}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: raw }),
      });

      if (res.ok) {
        setMessageType('ok');
        setMessage('Saved! Vercel is redeploying...');
      } else {
        const err = await res.json();
        setMessageType('err');
        setMessage(err.error || 'Save failed');
      }
    } catch {
      setMessageType('err');
      setMessage('Request failed');
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    router.push('/admin/dashboard');
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={handleCancel}
            className="text-[#555] text-xs hover:text-[#888] transition-colors"
          >
            ← Back
          </button>
          <h1 className="text-lg font-semibold font-mono">{dir}</h1>
        </div>
        <div className="flex items-center gap-3">
          {message && (
            <span className={messageType === 'ok' ? 'text-[#4ade80] text-xs' : 'text-red-400 text-xs'}>
              {message}
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-[#e0e0e0] text-[#0a0a0a] text-xs font-medium px-4 py-1.5 rounded-md hover:bg-white disabled:opacity-40 transition-colors"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Editor + Preview split */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-[calc(100vh-120px)]">
        {/* Left: editor */}
        <div className="flex flex-col">
          <div className="text-[#444] text-[10px] uppercase tracking-wider mb-1.5">Markdown</div>
          <textarea
            value={raw}
            onChange={e => setRaw(e.target.value)}
            className="flex-1 w-full bg-[#0d0d0d] border border-[#1a1a1a] rounded-md p-3 text-xs text-[#e0e0e0] font-mono resize-none focus:outline-none focus:border-[#333] leading-relaxed"
            spellCheck={false}
          />
        </div>

        {/* Right: preview */}
        <div className="flex flex-col overflow-hidden">
          <div className="text-[#444] text-[10px] uppercase tracking-wider mb-1.5">Preview</div>
          <div className="flex-1 overflow-y-auto bg-[#0d0d0d] border border-[#1a1a1a] rounded-md p-4 markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{raw.replace(/^---[\s\S]*?---\n?/, '')}</ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
