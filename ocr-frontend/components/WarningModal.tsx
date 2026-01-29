import React from 'react';

interface WarningModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  message: string;
}

export default function WarningModal({ isOpen, onClose, title, message }: WarningModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 transform transition-all animate-in fade-in zoom-in-95 duration-200">
        <div className="flex flex-col items-center text-center">
          <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mb-4">
            <svg 
              className="w-8 h-8 text-amber-600" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" 
              />
            </svg>
          </div>
          
          <h3 className="text-xl font-bold text-gray-900 mb-2">
            {title}
          </h3>
          
          <div className="text-gray-600 mb-8 leading-relaxed whitespace-pre-line">
            {message}
          </div>
          
          <button
            onClick={onClose}
            className="w-full sm:w-auto min-w-[120px] px-6 py-2.5 bg-gray-900 text-white text-sm font-semibold rounded-lg hover:bg-gray-800 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-900"
          >
            Okay
          </button>
        </div>
      </div>
    </div>
  );
}