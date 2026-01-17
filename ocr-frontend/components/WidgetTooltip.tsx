import React from 'react';

interface WidgetTooltipProps {
  title: string;
  description: string;
  formulas?: { label: string; formula: string }[];
  className?: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export default function WidgetTooltip({ title, description, formulas, className = "", position = 'top' }: WidgetTooltipProps) {
  
  const positionClasses = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  const arrowClasses = {
    top: "top-full left-1/2 -translate-x-1/2 -mt-1 border-t-white border-b-transparent border-l-transparent border-r-transparent",
    bottom: "bottom-full left-1/2 -translate-x-1/2 -mb-1 border-b-white border-t-transparent border-l-transparent border-r-transparent",
    left: "left-full top-1/2 -translate-y-1/2 -ml-1 border-l-white border-r-transparent border-t-transparent border-b-transparent",
    right: "right-full top-1/2 -translate-y-1/2 -mr-1 border-r-white border-l-transparent border-t-transparent border-b-transparent",
  };

  return (
    <div className={`group/tooltip relative inline-block align-middle ml-2 ${className}`}>
      <span className="w-4 h-4 rounded-full border border-neutral-400 text-neutral-400 flex items-center justify-center text-[10px] font-serif italic cursor-help hover:border-[#FF5E00] hover:text-[#FF5E00] hover:bg-[#FFF5F0] transition-colors">
        i
      </span>
      <div className={`absolute z-[1000] ${positionClasses[position]} hidden group-hover/tooltip:block w-72 p-4 bg-white border border-slate-200 rounded-lg shadow-xl text-left text-sm font-normal normal-case`}>
        <h4 className="font-bold text-slate-900 mb-2 border-b pb-1">{title}</h4>
        <p className="text-slate-600 text-xs mb-3 leading-relaxed">{description}</p>
        
        {formulas && formulas.length > 0 && (
          <div className="space-y-2 bg-slate-50 p-2 rounded border border-slate-100">
             <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mb-1">Calculations</p>
             {formulas.map((item, idx) => (
               <div key={idx} className="mb-1 last:mb-0">
                 <span className="text-xs font-medium text-slate-700 block">{item.label}:</span>
                 <code className="block text-[10px] bg-white border border-slate-200 rounded px-1.5 py-0.5 mt-0.5 text-slate-600 font-mono break-all">
                   {item.formula}
                 </code>
               </div>
             ))}
          </div>
        )}
        
        {/* Arrow */}
        <div className={`absolute border-4 ${arrowClasses[position]}`} />
      </div>
    </div>
  );
}