import styled from "styled-components";


export const Container = styled.footer `
  width: ${props => (props.scrl ? 'calc(100% - 24px)' : 'calc(100% - 16px)')};
  margin: ${props => (props.scrl ? '8px 16px 8px 8px' : '8px')};
`;

export const Wrapper = styled.div `
  display: flex;
  width: calc(100% - 16px);
  height: 30px;
  padding: 0 8px;
  align-items: center;
  flex-wrap: wrap;
  border-top: 1px solid #bfbfbf;
  overflow-y: hidden;
`;

export const Text = styled.p `
  margin: 0;
  font-size: 0.8em;
  color: #333;
  white-space: pre;

  & > a {
    text-decoration: none;
    color: #333;
  }
`;