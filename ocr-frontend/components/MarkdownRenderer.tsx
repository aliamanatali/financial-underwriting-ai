"use client";

import React from "react";

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  // Parse markdown content into React elements
  const parseMarkdown = (text: string): React.ReactNode[] => {
    const lines = text.split("\n");
    const elements: React.ReactNode[] = [];
    let inList = false;
    let listItems: string[] = [];
    let elementKey = 0;

    const processInlineMarkdown = (line: string): React.ReactNode => {
      return processTextContent(line);
    };

    const processTextContent = (line: string): React.ReactNode => {
      // Process bold (**text** or __text__)
      const parts: React.ReactNode[] = [];
      let remaining = line;
      let key = 0;

      // Bold pattern
      const boldRegex = /\*\*(.+?)\*\*/g;
      remaining = remaining.replace(boldRegex, "§BOLD§$1§/BOLD§");

      // Split and process
      const segments = remaining.split(/§(BOLD|\/BOLD)§/);
      let isBold = false;

      segments.forEach((segment) => {
        if (segment === "BOLD") {
          isBold = true;
          return;
        }
        if (segment === "/BOLD") {
          isBold = false;
          return;
        }
        if (segment) {
          if (isBold) {
            parts.push(
              <strong key={key++} className="font-semibold">
                {segment}
              </strong>
            );
          } else {
            parts.push(<span key={key++}>{segment}</span>);
          }
        }
      });

      return parts.length > 0 ? parts : line;
    };

    lines.forEach((line, index) => {
      const trimmedLine = line.trim();

      // Handle headers
      if (trimmedLine.startsWith("### ")) {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-5 mb-4 space-y-1.5"
            >
              {listItems.map((item, i) => (
                <li key={i}>{processTextContent(item)}</li>
              ))}
            </ul>
          );
          listItems = [];
          inList = false;
        }
        elements.push(
          <h3
            key={elementKey++}
            className="text-lg font-semibold text-neutral-900 mb-3 mt-6"
          >
            {processTextContent(trimmedLine.substring(4))}
          </h3>
        );
      } else if (trimmedLine.startsWith("## ")) {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-5 mb-4 space-y-1.5"
            >
              {listItems.map((item, i) => (
                <li key={i}>{processTextContent(item)}</li>
              ))}
            </ul>
          );
          listItems = [];
          inList = false;
        }
        elements.push(
          <h2
            key={elementKey++}
            className="text-xl font-semibold text-neutral-900 mb-3 mt-6"
          >
            {processTextContent(trimmedLine.substring(3))}
          </h2>
        );
      } else if (trimmedLine.startsWith("# ")) {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-5 mb-4 space-y-1.5"
            >
              {listItems.map((item, i) => (
                <li key={i}>{processTextContent(item)}</li>
              ))}
            </ul>
          );
          listItems = [];
          inList = false;
        }
        elements.push(
          <h1
            key={elementKey++}
            className="text-2xl font-bold text-neutral-900 mb-4 mt-6"
          >
            {processTextContent(trimmedLine.substring(2))}
          </h1>
        );
      }
      // Handle list items
      else if (trimmedLine.startsWith("* ") || trimmedLine.startsWith("- ")) {
        inList = true;
        listItems.push(trimmedLine.substring(2));
      }
      // Handle numbered list items
      else if (/^\d+\.\s/.test(trimmedLine)) {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-5 mb-4 space-y-1.5"
            >
              {listItems.map((item, i) => (
                <li key={i}>{processTextContent(item)}</li>
              ))}
            </ul>
          );
          listItems = [];
        }
        inList = true;
        listItems.push(trimmedLine.replace(/^\d+\.\s/, ""));
      }
      // Handle empty lines
      else if (trimmedLine === "") {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-5 mb-4 space-y-1.5"
            >
              {listItems.map((item, i) => (
                <li key={i}>{processTextContent(item)}</li>
              ))}
            </ul>
          );
          listItems = [];
          inList = false;
        }
      }
      // Handle regular paragraphs
      else {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-5 mb-4 space-y-1.5"
            >
              {listItems.map((item, i) => (
                <li key={i}>{processTextContent(item)}</li>
              ))}
            </ul>
          );
          listItems = [];
          inList = false;
        }
        elements.push(
          <p key={elementKey++} className="mb-4 leading-7">
            {processInlineMarkdown(trimmedLine)}
          </p>
        );
      }
    });

    // Handle remaining list items
    if (inList && listItems.length > 0) {
      elements.push(
        <ul
          key={`final-list-${elementKey++}`}
          className="list-disc pl-5 mb-4 space-y-1.5"
        >
          {listItems.map((item, i) => (
            <li key={i}>{processTextContent(item)}</li>
          ))}
        </ul>
      );
    }

    return elements;
  };

  return (
    <div className="prose prose-neutral max-w-none">
      {parseMarkdown(content)}
    </div>
  );
}
