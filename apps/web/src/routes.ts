import { createBrowserRouter } from 'react-router';
import RootLayout from './components/RootLayout';
import Home from './routes/Home';
import Login from './routes/Login';
import MyPageAccount from './routes/MyPageAccount';
import MyPageRegion from './routes/MyPageRegion';
import NotFound from './routes/NotFound';
import RegionComparison from './routes/RegionComparison';
import RegionDashboard from './routes/RegionDashboard';
import SignUp from './routes/SignUp';
import SignUpRegion from './routes/SignUpRegion';

export const router = createBrowserRouter([
  {
    Component: RootLayout,
    children: [
      {
        index: true,
        Component: Home,
      },
      {
        path: 'login',
        Component: Login,
      },
      {
        path: 'signup',
        Component: SignUp,
      },
      {
        path: 'signup/region',
        Component: SignUpRegion,
      },
      {
        path: 'dashboard/:regionCode',
        Component: RegionDashboard,
      },
      {
        path: 'compare',
        Component: RegionComparison,
      },
      {
        path: 'mypage/region',
        Component: MyPageRegion,
      },
      {
        path: 'mypage/account',
        Component: MyPageAccount,
      },
      {
        path: '*',
        Component: NotFound,
      },
    ],
  },
]);
