import styled from "styled-components";

import { SvgImg } from "../components/component/pages/SvgImgJs";
import { Calendar } from "../components/component/pages/CalendarJs";


export const Body = styled.div `
  display: flex;
  width: 100%;
  heihgt: 100%;
  flex-wrap: wrap;
`;

export const Home = () => {
  return (
    <>
      <Body>
        <SvgImg />
        <Calendar />
      </Body>
    </>
  )
}