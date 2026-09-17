import type { ReactNode } from 'react';
import { NavLink } from 'react-router';
import { cn } from '../../utils/cn';

const navItems = [
  { to: '/mypage/region', label: '★ 관심 지역 설정' },
  { to: '/mypage/account', label: '회원 정보' },
];

interface MyPageLayoutProps {
  children: ReactNode;
}

function MyPageLayout({ children }: MyPageLayoutProps) {
  return (
    <div className="flex flex-1 flex-col bg-muted md:flex-row">
      <aside className="flex w-full shrink-0 flex-col gap-2 border-b bg-card p-6 md:w-65 md:border-b-0 md:border-r">
        <h2 className="text-heading">마이페이지</h2>
        <nav
          aria-label="마이페이지 메뉴"
          className="flex flex-wrap gap-2 md:flex-col"
        >
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex h-12 items-center rounded-lg px-3 text-label-small outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/40',
                  isActive
                    ? 'bg-secondary text-secondary-foreground'
                    : 'text-muted-foreground hover:bg-muted'
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col gap-3 p-7">{children}</div>
    </div>
  );
}

export default MyPageLayout;
