import React from 'react';

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  className = '',
  ...props
}) {
  const baseStyles = `
    inline-flex items-center justify-center
    font-medium cursor-pointer
    transition-all duration-200
    rounded-md border
    focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--color-primary)]
    disabled:opacity-50 disabled:cursor-not-allowed
  `;

  const variants = {
    primary: `
      bg-[var(--color-primary)] text-white border-[var(--color-primary)]
      hover:bg-[var(--color-primary-light)] hover:border-[var(--color-primary-light)]
    `,
    secondary: `
      bg-[var(--color-bg-secondary)] text-[var(--color-fg-primary)] border-[var(--color-border)]
      hover:bg-[var(--color-bg-tertiary)] hover:border-[var(--color-fg-tertiary)]
    `,
    ghost: `
      bg-transparent text-[var(--color-primary)] border-transparent
      hover:bg-[var(--color-bg-secondary)]
    `,
    danger: `
      bg-[var(--color-error)] text-white border-[var(--color-error)]
      hover:opacity-90
    `,
  };

  const sizes = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}

export default Button;
