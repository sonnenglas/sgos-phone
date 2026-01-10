import { ReactNode } from 'react';

interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'muted' | 'urgent' | 'positive' | 'negative' | 'info';
  children: ReactNode;
  size?: 'sm' | 'default';
}

export default function Badge({ variant = 'default', children, size = 'default' }: BadgeProps) {
  const variants = {
    default: 'bg-hover text-secondary',
    success: 'bg-black text-white',
    warning: 'bg-hover text-black',
    error: 'bg-black/10 text-black',
    muted: 'bg-border text-secondary',
    urgent: 'bg-red-500 text-white',
    positive: 'bg-green-100 text-green-800',
    negative: 'bg-red-100 text-red-800',
    info: 'bg-blue-100 text-blue-800',
  };

  const sizes = {
    sm: 'px-1.5 py-0.5 text-[10px]',
    default: 'px-2 py-0.5 text-xs',
  };

  return (
    <span className={`inline-block font-medium ${variants[variant]} ${sizes[size]}`}>
      {children}
    </span>
  );
}
