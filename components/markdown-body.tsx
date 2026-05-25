import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

interface MarkdownBodyProps {
  content: string;
}

const components: Components = {
  a: ({ href, children, ...props }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
      {children}
    </a>
  ),
};

export default function MarkdownBody({ content }: MarkdownBodyProps) {
  return (
    <div className="bg-[#0d0d0d] border border-[#1a1a1a] rounded-lg p-6 overflow-x-auto">
      <div className="md-content text-[0.92rem]">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
