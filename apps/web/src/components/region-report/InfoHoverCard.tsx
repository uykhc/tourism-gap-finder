import { Info } from 'lucide-react';
import { Button } from '../ui/button';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '../ui/hover-card';

interface InfoHoverCardProps {
  label: string;
  description: string;
}

// 지표·선정 기준 옆에 붙는 정보 아이콘. 호버(또는 포커스)하면 설명 카드가 뜬다.
function InfoHoverCard({ label, description }: InfoHoverCardProps) {
  return (
    <HoverCard>
      <HoverCardTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label={`${label} 설명 보기`}
          className="size-4.5 shrink-0 text-muted-foreground hover:bg-transparent hover:text-foreground"
        >
          <Info aria-hidden="true" className="size-3.5" strokeWidth={1.75} />
        </Button>
      </HoverCardTrigger>
      <HoverCardContent>{description}</HoverCardContent>
    </HoverCard>
  );
}

export default InfoHoverCard;
