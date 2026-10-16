import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const badgeVariants = {
  default: 'bg-th-surface-el text-th-text-secondary border-th-border',
  success: 'bg-th-success-tint text-th-success border-th-border',
  warning: 'bg-th-warning-tint text-th-warning border-th-border',
  danger: 'bg-th-danger-tint text-th-danger border-th-border',
  accent: 'bg-th-accent-sec text-white border-transparent',
  brand: 'bg-th-brand-tint text-th-brand border-th-border',
};

export const Badge = ({
  children,
  variant = 'default',
  className,
  dot = false,
}) => {
  return (
    <div
      className={twMerge(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border',
        badgeVariants[variant],
        className
      )}
    >
      {dot && (
        <span
          className={clsx(
            'w-1.5 h-1.5 rounded-full mr-1.5',
            variant === 'default' && 'bg-th-text-muted',
            variant === 'success' && 'bg-th-success',
            variant === 'warning' && 'bg-th-warning',
            variant === 'danger' && 'bg-th-danger',
            variant === 'brand' && 'bg-th-brand',
            variant === 'accent' && 'bg-white'
          )}
        />
      )}
      {children}
    </div>
  );
};
