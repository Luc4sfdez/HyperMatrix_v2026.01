import React from 'react';

export function Card({
  children,
  className = '',
  hoverable = false,
  ...props
}) {
  return (
    <div
      className={`
        bg-[var(--color-bg-primary)]
        border border-[var(--color-border)]
        rounded-lg
        p-6
        shadow-sm
        transition-all duration-200
        ${hoverable ? 'hover:shadow-md hover:border-[var(--color-primary)]' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={`pb-4 border-b border-[var(--color-border)] mb-4 ${className}`}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className = '' }) {
  return (
    <h2 className={`text-xl font-semibold text-[var(--color-fg-primary)] ${className}`}>
      {children}
    </h2>
  );
}

export function CardContent({ children, className = '' }) {
  return (
    <div className={`text-[var(--color-fg-secondary)] ${className}`}>
      {children}
    </div>
  );
}

export function CardFooter({ children, className = '' }) {
  return (
    <div className={`pt-4 border-t border-[var(--color-border)] mt-4 flex gap-2 justify-end ${className}`}>
      {children}
    </div>
  );
}

export default Card;
