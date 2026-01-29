import React from 'react';

interface TooltipProps {
  text: string;
  children: React.ReactNode;
}

const Tooltip: React.FC<TooltipProps> = ({ text, children }) => {
  return (
    <div className="relative flex items-center group">
      {children}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max max-w-xs bg-neutral-800 text-white text-xs rounded-md shadow-lg p-2 opacity-0 group-hover:opacity-100 transition-all duration-300 ease-in-out transform group-hover:scale-100 scale-95 pointer-events-none z-50">
        <span className="font-bold">FORMULA:</span> {text}
        <svg className="absolute text-neutral-800 h-2 w-full left-0 top-full" x="0px" y="0px" viewBox="0 0 255 255" xmlSpace="preserve">
          <polygon className="fill-current" points="0,0 127.5,127.5 255,0"/>
        </svg>
      </div>
    </div>
  );
};

export default Tooltip;