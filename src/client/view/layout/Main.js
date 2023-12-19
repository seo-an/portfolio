import { Outlet } from 'react-router-dom';

import styled from 'styled-components';


export const MainWrapper = styled.main `
  display: block;
  width: ${props => (props.scrl ? 'calc(100% - 24px)' : 'calc(100% - 16px)')};
  height: 100%;
  margin: ${props => (props.scrl ? '0 16px 0 8px' : '0 8px')};
  grid-row: 2;
`;

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