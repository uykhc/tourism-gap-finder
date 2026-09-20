import * as HoverCardPrimitive from '@radix-ui/react-hover-card';
import type { ComponentProps } from 'react';
import { cn } from '../../utils/cn';

function HoverCard(props: ComponentProps<typeof HoverCardPrimitive.Root>) {
  return (
    <HoverCardPrimitive.Root openDelay={150} closeDelay={100} {...props} />
  );
}

function HoverCardTrigger(
  props: ComponentProps<typeof HoverCardPrimitive.Trigger>
) {
  return <HoverCardPrimitive.Trigger {...props} />;
}

function HoverCardContent({
  className,
  align = 'start',
  sideOffset = 8,
  ...props
}: ComponentProps<typeof HoverCardPrimitive.Content>) {
  return (
    <HoverCardPrimitive.Portal>
      <HoverCardPrimitive.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-50 w-72 rounded-lg border bg-card p-3.5 text-body-small text-muted-foreground shadow-xl outline-none',
          className
        )}
        {...props}
      />
    </HoverCardPrimitive.Portal>
  );
}

export { HoverCard, HoverCardContent, HoverCardTrigger };
