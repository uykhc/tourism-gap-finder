import { Outlet } from 'react-router';
import useAccessToken from '../hooks/useAccessToken';
import useCurrentUserQuery from '../hooks/useCurrentUserQuery';
import useLogoutMutation from '../hooks/useLogoutMutation';
import Header from './Header';

function RootLayout() {
  const accessToken = useAccessToken();
  const currentUserQuery = useCurrentUserQuery();
  const logoutMutation = useLogoutMutation();

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      {accessToken && currentUserQuery.data ? (
        <Header
          variant="authenticated"
          isLoggingOut={logoutMutation.isPending}
          onLogout={() => logoutMutation.mutate()}
        />
      ) : (
        <Header />
      )}
      <main className="flex flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  );
}

export default RootLayout;
