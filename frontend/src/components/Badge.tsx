import { ReactNode } from 'react';

interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'muted';
  children: ReactNode;
}

export default function Badge({ variant = 'default', children }: BadgeProps) {
  const variants = {
    default: 'bg-hover text-secondary',
    success: 'bg-black text-white',
    warning: 'bg-hover text-black',
    error: 'bg-black/10 text-black',
    muted: 'bg-border text-secondary',
  };

  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium ${variants[variant]}`}>
      {children}
    </span>
  );
}
