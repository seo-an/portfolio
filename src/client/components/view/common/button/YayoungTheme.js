import styled from "styled-components";

import { ReactComponent as Tree } from "../../icon/svg/tree.svg";

export const Wrapper = styled.div `
  display: flex;
  min-width: 60px;
`

export const Button = styled.button `
  display: flex;
  line-height: 25px;
  align-items: center;
  font-size: 16px;
  background-color: white;
  border-color: #ff8a34;
  border-width: 1px;
  border-radius: 4px;
  border-style: none;

  &:active {
    border-style: solid;
  }
`

export const YayoungTheme = () => {
  return (
    <Wrapper>
      <Button>글쓰기<Tree></Tree></Button>
    </Wrapper>
  )
}