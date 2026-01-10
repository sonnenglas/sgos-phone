import { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md';
  children: ReactNode;
  loading?: boolean;
}

export default function Button({
  variant = 'primary',
  size = 'md',
  children,
  loading,
  disabled,
  className = '',
  ...props
}: ButtonProps) {
  const baseStyles = 'font-medium transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed';

  const variants = {
    primary: 'bg-black text-white hover:bg-black/80',
    secondary: 'bg-white text-black border border-border hover:bg-hover',
    danger: 'bg-white text-red-600 border border-red-200 hover:bg-red-50 hover:border-red-300',
    ghost: 'bg-transparent text-secondary hover:text-black hover:bg-hover',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? 'Working...' : children}
    </button>
  );
}
