import React, { useMemo } from 'react';
import hljs from 'highlight.js';

export interface CodeBlockProps {
  code: string;
  language?: string;
  fontSize?: number;
  lineHeight?: number;
  style?: React.CSSProperties;
  className?: string;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({
  code,
  language = 'typescript',
  fontSize = 22,
  lineHeight = 1.6,
  style,
  className,
}) => {
  const highlightedHtml = useMemo(() => {
    try {
      if (language && hljs.getLanguage(language)) {
        return hljs.highlight(code.trim(), { language }).value;
      }
      return hljs.highlightAuto(code.trim()).value;
    } catch {
      return code.trim();
    }
  }, [code, language]);

  return (
    <pre
      className={className}
      style={{
        margin: 0,
        fontFamily: "'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace",
        fontSize,
        lineHeight,
        color: '#E2E8F0',
        whiteSpace: 'pre',
        overflow: 'hidden',
        background: 'transparent',
        ...style,
      }}
      dangerouslySetInnerHTML={{ __html: highlightedHtml }}
    />
  );
};
