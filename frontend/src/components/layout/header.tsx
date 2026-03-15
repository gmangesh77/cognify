interface HeaderProps {
  title: string;
  subtitle: string;
  children?: React.ReactNode;
}

export function Header({ title, subtitle, children }: HeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight text-neutral-900">
          {title}
        </h1>
        <p className="mt-1 text-sm text-neutral-500">{subtitle}</p>
      </div>
      {children && <div className="flex items-center gap-3">{children}</div>}
    </div>
  );
}
