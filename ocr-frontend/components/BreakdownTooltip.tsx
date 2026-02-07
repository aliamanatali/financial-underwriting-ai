import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { StandardizedExpense } from "@/lib/types";

interface BreakdownTooltipProps {
  items: StandardizedExpense[];
  formatCurrency: (val: number) => string;
  className?: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export default function BreakdownTooltip({ items, formatCurrency, className = "", position = 'top' }: BreakdownTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);

  const updatePosition = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const scrollY = window.scrollY;
      const scrollX = window.scrollX;

      let top = 0;
      let left = 0;

      if (position === 'top') {
        top = rect.top + scrollY - 10;
        left = rect.left + scrollX + (rect.width / 2);
      } else if (position === 'bottom') {
        top = rect.bottom + scrollY + 10;
        left = rect.left + scrollX + (rect.width / 2);
      } else if (position === 'left') {
        top = rect.top + scrollY + (rect.height / 2);
        left = rect.left + scrollX - 10;
      } else if (position === 'right') {
        top = rect.top + scrollY + (rect.height / 2);
        left = rect.right + scrollX + 10;
      }

      setCoords({ top, left });
    }
  };

  const handleMouseEnter = () => {
    updatePosition();
    setIsVisible(true);
  };

  const handleMouseLeave = () => {
    setIsVisible(false);
  };

  useEffect(() => {
    if (isVisible) {
      window.addEventListener('scroll', updatePosition, true);
      window.addEventListener('resize', updatePosition);
      return () => {
        window.removeEventListener('scroll', updatePosition, true);
        window.removeEventListener('resize', updatePosition);
      };
    }
  }, [isVisible]);

  return (
    <>
      <div 
        ref={triggerRef}
        className={`inline-block ${className}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <span className="cursor-help">
           <span className="w-4 h-4 rounded-full border border-neutral-400 text-neutral-400 flex items-center justify-center text-[10px] font-serif italic hover:border-[#FF5E00] hover:text-[#FF5E00] hover:bg-[#FFF5F0] transition-colors bg-white">
              i
           </span>
        </span>
      </div>

      {isVisible && (
        <PortalTooltip 
          items={items}
          formatCurrency={formatCurrency}
          top={coords.top} 
          left={coords.left}
          position={position}
        />
      )}
    </>
  );
}

function PortalTooltip({ items, formatCurrency, top, left, position }: any) {
  if (typeof document === 'undefined') return null;

  return createPortal(
    <div 
      className="absolute z-[9999] w-96 p-0 bg-white border border-slate-200 rounded-lg shadow-xl text-left text-sm font-normal normal-case pointer-events-none transition-opacity duration-200 overflow-hidden"
      style={{ 
        top: top, 
        left: left,
        transform: getTransform(position)
      }}
    >
      <div className="bg-slate-50 px-4 py-2 border-b border-slate-100 flex justify-between items-center">
        <h4 className="font-bold text-slate-900 text-xs uppercase tracking-wider">Breakdown</h4>
        <span className="text-[10px] text-slate-500">{items.length} items</span>
      </div>
      
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 text-slate-500 sticky top-0">
            <tr>
              <th className="px-3 py-1.5 text-left font-medium">Description</th>
              <th className="px-3 py-1.5 text-right font-medium">Amount</th>
              <th className="px-3 py-1.5 text-right font-medium">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((item: StandardizedExpense, idx: number) => (
              <tr key={idx} className="hover:bg-slate-50">
                <td className="px-3 py-1.5 text-slate-700 truncate max-w-[150px]" title={item.original_text}>
                  {item.original_text}
                </td>
                <td className="px-3 py-1.5 text-slate-900 text-right font-mono">
                  {formatCurrency(item.amount)}
                </td>
                <td className="px-3 py-1.5 text-slate-500 text-right truncate max-w-[80px]" title={item.audit_log?.source}>
                  {item.audit_log?.source || "Unknown"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <div className="bg-slate-50 px-4 py-2 border-t border-slate-100 flex justify-between items-center">
        <span className="text-xs font-bold text-slate-700">Total</span>
        <span className="text-xs font-bold text-slate-900 font-mono">
          {formatCurrency(items.reduce((sum: number, item: StandardizedExpense) => sum + item.amount, 0))}
        </span>
      </div>
    </div>,
    document.body
  );
}

function getTransform(position: string) {
  switch (position) {
    case 'top': return 'translate(-50%, -100%)';
    case 'bottom': return 'translate(-50%, 0)';
    case 'left': return 'translate(-100%, -50%)';
    case 'right': return 'translate(0, -50%)';
    default: return 'translate(-50%, -100%)';
  }
}