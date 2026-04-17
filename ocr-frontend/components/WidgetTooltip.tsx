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
  const [effectivePosition, setEffectivePosition] = useState(position);
  const triggerRef = useRef<HTMLDivElement>(null);

  // Estimated tooltip height to decide whether to flip direction
  const TOOLTIP_HEIGHT_EST = 200;
  const TOOLTIP_WIDTH = 288; // w-72 = 18rem = 288px
  const SAFE_MARGIN = 10;

  const updatePosition = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const scrollY = window.scrollY;
    const scrollX = window.scrollX;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let top = 0;
    let left = 0;
    let effective = position;

    if (position === 'top' || position === 'bottom') {
      // Horizontal center
      left = rect.left + scrollX + rect.width / 2;
      // Clamp horizontally so tooltip doesn't overflow viewport edges
      const halfW = TOOLTIP_WIDTH / 2;
      if (left - halfW < scrollX + SAFE_MARGIN) left = scrollX + SAFE_MARGIN + halfW;
      if (left + halfW > scrollX + vw - SAFE_MARGIN) left = scrollX + vw - SAFE_MARGIN - halfW;

      if (position === 'top') {
        // Flip to bottom if tooltip would overflow above viewport
        if (rect.top - TOOLTIP_HEIGHT_EST - SAFE_MARGIN < 0) {
          effective = 'bottom';
          top = rect.bottom + scrollY + SAFE_MARGIN;
        } else {
          effective = 'top';
          top = rect.top + scrollY - SAFE_MARGIN;
        }
      } else {
        // Flip to top if tooltip would overflow below viewport
        if (rect.bottom + TOOLTIP_HEIGHT_EST + SAFE_MARGIN > vh) {
          effective = 'top';
          top = rect.top + scrollY - SAFE_MARGIN;
        } else {
          effective = 'bottom';
          top = rect.bottom + scrollY + SAFE_MARGIN;
        }
      }
    } else if (position === 'left') {
      top = rect.top + scrollY + rect.height / 2;
      left = rect.left + scrollX - SAFE_MARGIN;
      effective = 'left';
    } else if (position === 'right') {
      top = rect.top + scrollY + rect.height / 2;
      left = rect.right + scrollX + SAFE_MARGIN;
      effective = 'right';
    }

    setCoords({ top, left });
    setEffectivePosition(effective);
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
  }, [isVisible]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div
        ref={triggerRef}
        className={`inline-block align-middle ml-1.5 ${className}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <span className="w-4 h-4 rounded-full border border-[#CBD5E1] text-[#94A3B8] flex items-center justify-center text-[10px] font-serif italic cursor-help hover:border-[#F97316] hover:text-[#F97316] hover:bg-[rgba(249,115,22,0.06)] transition-colors">
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
          position={effectivePosition}
        />
      )}
    </>
  );
}

function PortalTooltip({ title, description, formulas, top, left, position }: {
  title: string;
  description: string;
  formulas?: { label: string; formula: string }[];
  top: number;
  left: number;
  position: string;
}) {
  if (typeof document === 'undefined') return null;

  return createPortal(
    <div
      className="absolute z-[9999] w-72 pointer-events-none"
      style={{ top, left, transform: getTransform(position) }}
    >
      <div className="bg-white border border-[#E2E8F0] rounded-xl shadow-[0_8px_30px_rgba(0,0,0,0.12)] p-4 text-left text-sm font-normal normal-case">
        <h4 className="text-xs font-semibold text-[#0F172A] mb-1.5 border-b border-[#F1F5F9] pb-1.5">{title}</h4>
        <p className="text-[#64748B] text-xs mb-3 leading-relaxed">{description}</p>

        {formulas && formulas.length > 0 && (
          <div className="space-y-1.5 bg-[#F8FAFC] p-2.5 rounded-lg border border-[#E2E8F0]">
            <p className="text-[9px] text-[#94A3B8] font-semibold uppercase tracking-widest mb-1.5">Calculations</p>
            {formulas.map((item, idx) => (
              <div key={idx} className="mb-1 last:mb-0">
                <span className="text-[10px] font-medium text-[#475569] block">{item.label}:</span>
                <code className="block text-[10px] bg-white border border-[#E2E8F0] rounded px-1.5 py-0.5 mt-0.5 text-[#475569] font-mono break-words">
                  {item.formula}
                </code>
              </div>
            ))}
          </div>
        )}
      </div>
      {/* Arrow */}
      {position === 'top' && (
        <div className="absolute left-1/2 -translate-x-1/2 top-full">
          <div className="w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-[#E2E8F0]" />
          <div className="w-0 h-0 border-l-[5px] border-r-[5px] border-t-[5px] border-l-transparent border-r-transparent border-t-white -mt-[7px] translate-x-[-5px]" />
        </div>
      )}
      {position === 'bottom' && (
        <div className="absolute left-1/2 -translate-x-1/2 bottom-full">
          <div className="w-0 h-0 border-l-[6px] border-r-[6px] border-b-[6px] border-l-transparent border-r-transparent border-b-[#E2E8F0]" />
          <div className="w-0 h-0 border-l-[5px] border-r-[5px] border-b-[5px] border-l-transparent border-r-transparent border-b-white mt-[1px] translate-x-[-5px]" />
        </div>
      )}
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
