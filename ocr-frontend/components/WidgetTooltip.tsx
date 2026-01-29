import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';

interface WidgetTooltipProps {
  title: string;
  description: string;
  formulas?: { label: string; formula: string }[];
  className?: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export default function WidgetTooltip({ title, description, formulas, className = "", position = 'top' }: WidgetTooltipProps) {
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

      // Basic positioning logic - can be expanded for other positions if needed
      // Currently optimizing for 'top' as default
      if (position === 'top') {
        top = rect.top + scrollY - 10; // 10px spacing above
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

  // Re-calculate on scroll or resize to keep it attached
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
        className={`inline-block align-middle ml-2 ${className}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <span className="w-4 h-4 rounded-full border border-neutral-400 text-neutral-400 flex items-center justify-center text-[10px] font-serif italic cursor-help hover:border-[#FF5E00] hover:text-[#FF5E00] hover:bg-[#FFF5F0] transition-colors">
          i
        </span>
      </div>

      {isVisible && (
        <PortalTooltip 
          title={title} 
          description={description} 
          formulas={formulas} 
          top={coords.top} 
          left={coords.left}
          position={position}
        />
      )}
    </>
  );
}

function PortalTooltip({ title, description, formulas, top, left, position }: any) {
  // Use a portal to render outside the current DOM hierarchy (e.g. outside overflow:hidden containers)
  if (typeof document === 'undefined') return null;

  return createPortal(
    <div 
      className="absolute z-[9999] w-72 p-4 bg-white border border-slate-200 rounded-lg shadow-xl text-left text-sm font-normal normal-case pointer-events-none transition-opacity duration-200"
      style={{ 
        top: top, 
        left: left,
        transform: getTransform(position)
      }}
    >
      <h4 className="font-bold text-slate-900 mb-2 border-b pb-1">{title}</h4>
      <p className="text-slate-600 text-xs mb-3 leading-relaxed">{description}</p>
      
      {formulas && formulas.length > 0 && (
        <div className="space-y-2 bg-slate-50 p-2 rounded border border-slate-100">
            <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mb-1">Calculations</p>
            {formulas.map((item: any, idx: number) => (
              <div key={idx} className="mb-1 last:mb-0">
                <span className="text-xs font-medium text-slate-700 block">{item.label}:</span>
                <code className="block text-[10px] bg-white border border-slate-200 rounded px-1.5 py-0.5 mt-0.5 text-slate-600 font-mono break-all">
                  {item.formula}
                </code>
              </div>
            ))}
        </div>
      )}
      
      {/* CSS Arrow could be added here if needed, but positioning logic gets complex with portals */}
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