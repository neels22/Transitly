import { useEffect, useState } from 'react';

interface NotificationProps {
  message: string;
  type?: 'success' | 'error';
  isVisible: boolean;
  onClose: () => void;
  duration?: number; // in milliseconds, default 4000ms
}

export default function Notification({
  message,
  type,
  isVisible,
  onClose,
  duration = 4000,
}: NotificationProps) {
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    if (isVisible) {
      setIsAnimating(true);

      // Auto-dismiss after specified duration
      const timer = setTimeout(() => {
        setIsAnimating(false);
        // Wait for exit animation before calling onClose
        setTimeout(onClose, 300);
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [isVisible, duration, onClose]);

  const getTypeStyles = () => {
    switch (type) {
      case 'success':
        return 'bg-black border-gray-800 text-white';
      case 'error':
        return 'bg-white border-gray-200 text-red-600';
      default:
        return 'bg-black border-gray-800 text-white';
    }
  };

  if (!isVisible) return null;

  return (
    <div
      className={`
        fixed z-50 flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border font-medium
        transition-all duration-300 ease-in-out max-w-sm bottom-4 right-4
        ${getTypeStyles()}
        ${isAnimating ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2'}
      `}
    >
      <span className="flex-1 text-sm">{message}</span>
      <button
        onClick={() => {
          setIsAnimating(false);
          setTimeout(onClose, 300);
        }}
        className="ml-2 opacity-70 hover:opacity-100 transition-opacity duration-200 font-bold text-lg leading-none"
      >
        ×
      </button>
    </div>
  );
}
