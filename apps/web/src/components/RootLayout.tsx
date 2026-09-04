import { Outlet } from 'react-router';
import Header from './Header';

function RootLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <Header />
      <main className="flex flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  );
}

export default RootLayout;
