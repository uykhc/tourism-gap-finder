import type { ComponentProps } from 'react';
import { cn } from '../../utils/cn';

function Skeleton({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse rounded-lg bg-border/70', className)}
      {...props}
    />
  );
}

export { Skeleton };
