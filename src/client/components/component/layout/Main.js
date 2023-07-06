import { Outlet } from 'react-router-dom';

import { MainWrapper } from '../../view/layout/MainView';


const Main = ({ nowScroll }) => { 
  return (
    (nowScroll ? (
      <MainWrapper scrl>
        <Outlet />
      </MainWrapper>
    ) : (
      <MainWrapper >
        <Outlet />
      </MainWrapper>
    ))
  );
}

export default Main;