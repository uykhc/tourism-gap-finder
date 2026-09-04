import { Link } from 'react-router';
import { Button } from './ui/button';

interface GuestHeaderProps {
  variant?: 'guest';
}

interface AuthenticatedHeaderProps {
  variant: 'authenticated';
  onLogout: () => void;
}

type HeaderProps = GuestHeaderProps | AuthenticatedHeaderProps;

function Header(props: HeaderProps) {
  return (
    <header className="h-20 shrink-0 border-b border-border bg-card">
      <div className="mx-auto flex h-full w-full max-w-[1200px] items-center justify-between px-4 sm:px-8 lg:px-12">
        <Link
          to="/"
          className="flex min-w-0 items-start gap-2.5 whitespace-nowrap"
          aria-label="한끗 홈"
        >
          <span className="text-heading text-primary">韓끗</span>
          <span className="hidden text-label-small text-muted-foreground sm:block">
            관광 빈칸 분석
          </span>
        </Link>

        <nav
          className="flex shrink-0 items-center gap-2.5"
          aria-label="계정 메뉴"
        >
          {props.variant === 'authenticated' ? (
            <>
              <Button asChild variant="outline">
                <Link to="/mypage/account">내 정보</Link>
              </Button>
              <Button type="button" onClick={props.onLogout}>
                로그아웃
              </Button>
            </>
          ) : (
            <>
              <Button asChild variant="outline">
                <Link to="/login">로그인</Link>
              </Button>
              <Button asChild>
                <Link to="/signup">회원가입</Link>
              </Button>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

export default Header;
