import styled from 'styled-components';

import SetURL from './SetURL.js';

export const Wrapper = styled.nav `
  display: flex;
  position: sticky;
  top: 0;
  width: ${props => (props.scrl ? 'calc(100% - 24px)' : 'calc(100% - 16px)')};
  height: 60px;
  margin: ${props => (props.scrl ? '0 16px 0 8px' : '0 8px')};
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #bfbfbf;
  grid-row: 1;
`;

export const MenuForSetUrl = styled.div `
  display: flex;
  width: 100%;
  min-width: 60px;
  height: 60px;
  margin: 0px 8px;
  align-items: center;
  justify-content: center;

  & > a {
    display: flex;
    text-decoration: none;
    color: #333;
    font-size: 1em;
  }
`;

const Nav = ({ nowScroll }) => {
  return (
    (nowScroll ? (
      <>
        <Wrapper scrl>
          <SetURL />
        </Wrapper>
      </>
    ) : (
      <>
        <Wrapper>
          <SetURL />
        </Wrapper>
      </>
    ))
  )
}

export default Nav;