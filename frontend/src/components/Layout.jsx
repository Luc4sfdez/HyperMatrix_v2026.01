import React from 'react';

export function Layout({
  sidebar,
  header,
  children,
  className = '',
  rightPanelOpen = false,
  rightPanelWidth = 384, // w-96 = 384px
}) {
  return (
    <div className="flex h-screen bg-[var(--color-bg-primary)]">
      {/* Sidebar */}
      {sidebar && (
        <div className="flex-shrink-0 bg-[var(--color-bg-primary)] border-r border-[var(--color-border)] overflow-y-auto relative transition-all duration-200">
          {sidebar}
        </div>
      )}

      {/* Main content - shrinks when right panel is open */}
      <div
        className="flex-1 flex flex-col overflow-hidden min-w-0 transition-all duration-200"
        style={{ marginRight: rightPanelOpen ? `${rightPanelWidth}px` : 0 }}
      >
        {/* Header */}
        {header && (
          <header className="flex-shrink-0 bg-[var(--color-bg-primary)] border-b border-[var(--color-border)] px-6 py-3">
            {header}
          </header>
        )}

        {/* Content */}
        <main className={`flex-1 overflow-y-auto bg-[var(--color-bg-secondary)] ${className}`}>
          {children}
        </main>
      </div>
    </div>
  );
}

export function LayoutHeader({
  title,
  subtitle,
  actions,
  className = '',
}) {
  return (
    <div className={`flex items-center gap-4 ${className}`}>
      <div>
        <h1 className="text-xl font-semibold text-[var(--color-fg-primary)] leading-tight">{title}</h1>
        {subtitle && (
          <p className="text-xs text-[var(--color-fg-secondary)]">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

export function LayoutContent({ children, className = '' }) {
  return (
    <div className={`bg-[var(--color-bg-primary)] rounded-lg border border-[var(--color-border)] p-6 ${className}`}>
      {children}
    </div>
  );
}

export default Layout;
