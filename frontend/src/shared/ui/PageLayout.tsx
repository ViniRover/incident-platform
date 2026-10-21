import type { ReactNode } from 'react';

export function PageLayout({ children }: { children: ReactNode }) {
  return <main>{children}</main>;
}
