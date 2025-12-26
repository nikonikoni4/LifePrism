import React, { memo } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check } from 'lucide-react';


interface MarkdownRendererProps {
    content: string;
    className?: string;
}

// 代码块组件 - 带复制功能
const CodeBlock: React.FC<{
    language: string;
    children: string;
}> = ({ language, children }) => {
    const [copied, setCopied] = React.useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(children);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative group my-3">
            {/* 语言标签和复制按钮 */}
            <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-4 py-2 bg-gray-800 rounded-t-lg border-b border-gray-700">
                <span className="text-xs text-gray-400 font-mono uppercase">{language || 'code'}</span>
                <button
                    onClick={handleCopy}
                    className="flex items-center gap-1.5 px-2 py-1 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
                >
                    {copied ? (
                        <>
                            <Check size={14} className="text-green-400" />
                            <span className="text-green-400">已复制</span>
                        </>
                    ) : (
                        <>
                            <Copy size={14} />
                            <span>复制</span>
                        </>
                    )}
                </button>
            </div>
            {/* 代码块内容 */}
            <SyntaxHighlighter
                language={language}
                style={oneDark}
                customStyle={{
                    margin: 0,
                    paddingTop: '3rem',
                    paddingBottom: '1rem',
                    borderRadius: '0.5rem',
                    fontSize: '0.875rem',
                    lineHeight: '1.5',
                }}
                showLineNumbers={children.split('\n').length > 3}
                lineNumberStyle={{
                    minWidth: '2.5em',
                    paddingRight: '1em',
                    color: '#6b7280',
                    userSelect: 'none',
                }}
            >
                {children}
            </SyntaxHighlighter>
        </div>
    );
};

// 内联代码组件
const InlineCode: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <code className="px-1.5 py-0.5 mx-0.5 bg-gray-100 text-indigo-600 rounded text-sm font-mono border border-gray-200">
        {children}
    </code>
);

const MarkdownRenderer: React.FC<MarkdownRendererProps> = memo(({ content, className = '' }) => {
    return (
        <div className={`markdown-content ${className}`}>
            <Markdown
                remarkPlugins={[remarkGfm]}
                components={{
                    // 代码块
                    code: ({ node, className, children, ...props }) => {
                        const match = /language-(\w+)/.exec(className || '');
                        const isInline = !match && !String(children).includes('\n');

                        if (isInline) {
                            return <InlineCode>{children}</InlineCode>;
                        }

                        return (
                            <CodeBlock language={match?.[1] || ''}>
                                {String(children).replace(/\n$/, '')}
                            </CodeBlock>
                        );
                    },
                    // 段落
                    p: ({ children }) => (
                        <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>
                    ),
                    // 标题
                    h1: ({ children }) => (
                        <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0 pb-2 border-b border-gray-200">{children}</h1>
                    ),
                    h2: ({ children }) => (
                        <h2 className="text-lg font-bold mb-2 mt-4 first:mt-0">{children}</h2>
                    ),
                    h3: ({ children }) => (
                        <h3 className="text-base font-semibold mb-2 mt-3 first:mt-0">{children}</h3>
                    ),
                    h4: ({ children }) => (
                        <h4 className="text-sm font-semibold mb-2 mt-2 first:mt-0">{children}</h4>
                    ),
                    // 列表
                    ul: ({ children }) => (
                        <ul className="list-disc list-inside mb-3 space-y-1 pl-2">{children}</ul>
                    ),
                    ol: ({ children }) => (
                        <ol className="list-decimal list-inside mb-3 space-y-1 pl-2">{children}</ol>
                    ),
                    li: ({ children }) => (
                        <li className="leading-relaxed">{children}</li>
                    ),
                    // 引用块
                    blockquote: ({ children }) => (
                        <blockquote className="border-l-4 border-indigo-400 bg-indigo-50 pl-4 pr-3 py-2 my-3 rounded-r-lg italic text-gray-700">
                            {children}
                        </blockquote>
                    ),
                    // 链接
                    a: ({ href, children }) => (
                        <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-indigo-600 hover:text-indigo-800 underline decoration-indigo-300 hover:decoration-indigo-500 transition-colors"
                        >
                            {children}
                        </a>
                    ),
                    // 强调
                    strong: ({ children }) => (
                        <strong className="font-semibold text-gray-900">{children}</strong>
                    ),
                    em: ({ children }) => (
                        <em className="italic text-gray-700">{children}</em>
                    ),
                    // 删除线
                    del: ({ children }) => (
                        <del className="text-gray-500 line-through">{children}</del>
                    ),
                    // 分割线
                    hr: () => (
                        <hr className="my-4 border-gray-200" />
                    ),
                    // 表格
                    table: ({ children }) => (
                        <div className="overflow-x-auto my-3">
                            <table className="min-w-full border border-gray-200 rounded-lg overflow-hidden">
                                {children}
                            </table>
                        </div>
                    ),
                    thead: ({ children }) => (
                        <thead className="bg-gray-50">{children}</thead>
                    ),
                    tbody: ({ children }) => (
                        <tbody className="divide-y divide-gray-200">{children}</tbody>
                    ),
                    tr: ({ children }) => (
                        <tr className="hover:bg-gray-50">{children}</tr>
                    ),
                    th: ({ children }) => (
                        <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider border-b border-gray-200">
                            {children}
                        </th>
                    ),
                    td: ({ children }) => (
                        <td className="px-3 py-2 text-sm text-gray-700 border-gray-200">
                            {children}
                        </td>
                    ),
                    // 图片
                    img: ({ src, alt }) => (
                        <img
                            src={src}
                            alt={alt}
                            className="max-w-full h-auto rounded-lg my-3 shadow-sm"
                        />
                    ),
                }}
            >
                {content}
            </Markdown>
        </div>
    );
});

MarkdownRenderer.displayName = 'MarkdownRenderer';

export default MarkdownRenderer;
