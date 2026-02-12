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
    let inTable = false;
    let tableRows: string[] = [];
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

    const renderTable = (rows: string[], key: number): React.ReactNode => {
      const data = rows.map((row) => {
        const content = row.trim();
        // Remove leading/trailing pipes
        const inner = content.replace(/^\||\|$/g, "");
        return inner.split("|").map((cell) => cell.trim());
      });

      if (data.length === 0) return null;

      const header = data[0];
      // Check for separator row (contains only -, :, |)
      let separatorIndex = -1;
      if (data.length > 1) {
        const secondRow = data[1];
        // Heuristic: if all cells contain only -, :, or whitespace
        const isSeparator =
          secondRow.every((cell) => /^[-:\s]+$/.test(cell)) &&
          secondRow.some((cell) => cell.includes("-"));
        if (isSeparator) {
          separatorIndex = 1;
        }
      }

      const bodyStart = separatorIndex !== -1 ? separatorIndex + 1 : 1;
      const body = data.slice(bodyStart);

      return (
        <div
          key={key}
          className="overflow-x-auto mb-4 border border-neutral-200 rounded-lg"
        >
          <table className="min-w-full divide-y divide-neutral-200 text-xs">
            <thead className="bg-neutral-50">
              <tr>
                {header.map((cell, i) => (
                  <th
                    key={i}
                    className="px-4 py-3 text-left font-medium text-neutral-900 tracking-wider"
                  >
                    {processTextContent(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-neutral-200">
              {body.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className={rowIndex % 2 === 0 ? "bg-white" : "bg-neutral-50/50"}
                >
                  {row.map((cell, cellIndex) => (
                    <td
                      key={cellIndex}
                      className="px-4 py-3 text-neutral-600 whitespace-pre-wrap"
                    >
                      {processTextContent(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    };

    lines.forEach((line, index) => {
      const trimmedLine = line.trim();

      // Handle Table
      if (trimmedLine.startsWith("|")) {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-4 mb-2 space-y-1"
            >
              {listItems.map((item, i) => (
                <li key={i}>{processTextContent(item)}</li>
              ))}
            </ul>
          );
          listItems = [];
          inList = false;
        }

        inTable = true;
        tableRows.push(trimmedLine);
        return; // Continue to next line
      }

      // If we were in a table but this line is not a table line, flush the table
      if (inTable) {
        elements.push(renderTable(tableRows, elementKey++));
        tableRows = [];
        inTable = false;
      }

      // Handle headers
      if (trimmedLine.startsWith("### ")) {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-4 mb-2 space-y-1"
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
            className="text-sm font-bold text-neutral-900 mb-2 mt-4"
          >
            {processTextContent(trimmedLine.substring(4))}
          </h3>
        );
      } else if (trimmedLine.startsWith("## ")) {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-4 mb-2 space-y-1"
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
            className="text-base font-bold text-neutral-900 mb-2 mt-4"
          >
            {processTextContent(trimmedLine.substring(3))}
          </h2>
        );
      } else if (trimmedLine.startsWith("# ")) {
        if (inList && listItems.length > 0) {
          elements.push(
            <ul
              key={`list-${elementKey++}`}
              className="list-disc pl-4 mb-2 space-y-1"
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
            className="text-lg font-bold text-neutral-900 mb-2 mt-4"
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
              className="list-disc pl-4 mb-2 space-y-1"
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
              className="list-disc pl-4 mb-2 space-y-1"
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
              className="list-disc pl-4 mb-2 space-y-1"
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
          <p key={elementKey++} className="mb-2 leading-relaxed">
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
          className="list-disc pl-4 mb-2 space-y-1"
        >
          {listItems.map((item, i) => (
            <li key={i}>{processTextContent(item)}</li>
          ))}
        </ul>
      );
    }

    // Handle remaining table
    if (inTable && tableRows.length > 0) {
      elements.push(renderTable(tableRows, elementKey++));
    }

    return elements;
  };

  return (
    <div className="text-xs leading-relaxed text-neutral-800 break-words space-y-1">
      {parseMarkdown(content)}
    </div>
  );
}
