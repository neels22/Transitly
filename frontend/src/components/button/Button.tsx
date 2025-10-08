interface ButtonProps {
  text: string;
  color?: string;
  rounded?: boolean;
  onClick?: () => void;
  size?: 'base' | 'lg' | string;
  bold?: boolean;
}

export default function Button({
    text,
    color = '#000',
    onClick,
    rounded,
    size = 'base',
    bold = true
}: ButtonProps) {

  const sizeClasses = (() => {
    switch (size) {
      case 'base':
        return 'px-4 py-2 text-sm';
      case 'lg':
        return 'px-10 py-3 text-lg';
      default:
        return 'px-4 py-2 text-sm';
    }
  })();

  const weightClass = bold ? 'font-bold' : 'font-normal';
  const baseClasses = `${sizeClasses} ${weightClass} text-white`;
  const roundedClasses = rounded
    ? 'rounded-full'
    : (size === 'lg' ? 'rounded-2xl' : 'rounded-xl');
  const className = `${baseClasses} ${roundedClasses}`.trim();

  return (
    <button
      className={className}
      style={{ backgroundColor: color }}
      onClick={onClick}
    >
      {text}
    </button>
  );
}
