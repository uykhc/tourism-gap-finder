import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import RegionSelector from '../region/RegionSelector';
import { Button } from '../ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../ui/dialog';

interface RegionChangeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function RegionChangeDialog({ open, onOpenChange }: RegionChangeDialogProps) {
  const navigate = useNavigate();
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) setSelectedRegionId(null);
  }, [open]);

  const handleComplete = (regionId: string) => {
    onOpenChange(false);
    navigate(`/dashboard/${regionId}`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <div className="flex flex-col gap-2">
          <DialogTitle>분석 지역 변경</DialogTitle>
          <DialogDescription>
            새로 확인할 시·도와 시·군·구를 선택해 주세요.
          </DialogDescription>
        </div>
        <RegionSelector
          value={selectedRegionId}
          onChange={setSelectedRegionId}
          onComplete={handleComplete}
          completeLabel="이 지역 보고서 보기"
        />
        <div className="flex justify-end">
          <DialogClose asChild>
            <Button type="button" variant="outline">
              닫기
            </Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default RegionChangeDialog;
