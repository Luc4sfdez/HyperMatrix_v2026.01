import React, { useState } from 'react';

export function Sidebar({
  children,
  width = '250px',
  className = '',
}) {
  return (
    <aside
      className={`
        bg-[var(--color-bg-primary)]
        border-r border-[var(--color-border)]
        overflow-y-auto
        ${className}
      `}
      style={{ width }}
    >
      {children}
    </aside>
  );
}

export function SidebarNav({ children, className = '' }) {
  return (
    <nav className={`p-4 ${className}`}>
      {children}
    </nav>
  );
}

export function SidebarNavGroup({
  title,
  children,
  defaultOpen = false,
  className = '',
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={`mb-2 ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          w-full text-left
          px-3 py-2
          text-xs font-semibold uppercase tracking-wider
          text-[var(--color-fg-secondary)]
          hover:text-[var(--color-fg-primary)]
          transition-colors duration-150
          flex items-center justify-between
          rounded-md
          hover:bg-[var(--color-bg-secondary)]
        `}
      >
        {title}
        <span className={`transform transition-transform ${isOpen ? 'rotate-90' : ''}`}>
          ▶
        </span>
      </button>
      {isOpen && (
        <div className="ml-2 border-l border-[var(--color-border)]">
          {children}
        </div>
      )}
    </div>
  );
}

export function SidebarNavItem({
  href = '#',
  active = false,
  children,
  className = '',
  ...props
}) {
  return (
    <a
      href={href}
      className={`
        block
        px-4 py-2 my-1 mx-2
        text-sm rounded-md
        transition-all duration-150
        ${
          active
            ? 'bg-[var(--color-primary)] text-white'
            : 'text-[var(--color-fg-secondary)] hover:text-[var(--color-fg-primary)] hover:bg-[var(--color-bg-secondary)]'
        }
        ${className}
      `}
      {...props}
    >
      {children}
    </a>
  );
}

export default Sidebar;
