import React, { forwardRef } from 'react';
import { twMerge } from 'tailwind-merge';

export const Card = forwardRef(({ className, children, elevated = false, ...props }, ref) => {
  return (
    <div
      ref={ref}
      className={twMerge(
        'bg-th-surface border border-th-border rounded-xl transition-colors duration-200 overflow-hidden',
        elevated ? 'shadow-elevated' : 'shadow-card',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
});

Card.displayName = 'Card';

export const CardHeader = ({ className, children, ...props }) => (
  <div
    className={twMerge('px-6 py-5 border-b border-th-border flex flex-col sm:flex-row sm:items-center justify-between gap-4', className)}
    {...props}
  >
    {children}
  </div>
);

export const CardTitle = ({ className, children, ...props }) => (
  <h3
    className={twMerge('text-lg font-semibold text-th-text-primary font-serif', className)}
    {...props}
  >
    {children}
  </h3>
);

export const CardDescription = ({ className, children, ...props }) => (
  <p
    className={twMerge('text-sm text-th-text-secondary mt-1', className)}
    {...props}
  >
    {children}
  </p>
);

export const CardContent = ({ className, children, ...props }) => (
  <div className={twMerge('p-6', className)} {...props}>
    {children}
  </div>
);
