import { Link } from 'react-router';
import { Button } from '../components/ui/button';

function NotFound() {
  return (
    <section className="mx-auto flex w-full max-w-[1200px] flex-1 flex-col items-start gap-4 px-4 py-10 sm:px-8 lg:px-12">
      <div className="space-y-2">
        <h1>페이지를 찾을 수 없습니다</h1>
        <p className="text-muted-foreground">
          요청한 주소가 올바른지 확인해 주세요.
        </p>
      </div>
      <Button asChild>
        <Link to="/">홈으로 돌아가기</Link>
      </Button>
    </section>
  );
}

export default NotFound;
