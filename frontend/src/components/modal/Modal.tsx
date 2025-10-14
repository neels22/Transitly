import React from 'react';

interface ModalProps {
  isOpen: boolean;
  mask?: boolean;
  backgroundColor?: string;
  width?: string;
  children: React.ReactNode;
  onClose: () => void;
}

export default function Modal({
  isOpen,
  onClose,
  mask = true,
  backgroundColor = '#F6F7FA',
  width,
  children
}: ModalProps) {
  if (!isOpen) return null;

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const modalStyle = {
    backgroundColor,
    ...(width && { width })
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={handleOverlayClick}
    >
      {mask && (
        <div className="absolute inset-0 bg-black/25" />
      )}
      
      <div 
        className="relative bg-white rounded-3xl px-6 py-12 max-w-md w-full mx-4"
        style={modalStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
