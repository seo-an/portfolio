import styled from "styled-components";

import { Link } from "react-router-dom";
// import { SvgImg } from "../components/component/pages/SvgImgJs";
// import { Calendar } from "../components/component/pages/CalendarJs";


export const Body = styled.div `
  display: flex;
  width: 100%;
  heihgt: 100%;
  flex-wrap: wrap;
`;

export const CardContainer = styled.div `
  display: flex;
  width: 100%;
  heihgt: 100%;
  margin: 30px 0;
  align-content: center;
  justify-content: space-evenly;
  flex-wrap: nowrap;
`;

export const CardWrapper = styled.div `
  display: flex;
  width: 200px;
  heihgt: 200px;
  border: 1px solid #000;
`;

export const Home = () => {
  return (
    <>
      <Body>
        <div>
          <p>자기소개</p>
        </div>
        <CardContainer>
          <CardWrapper>
            <Link to={`/calendar`} target={'_blank'}>순수 JS 캘린더</Link>
          </CardWrapper>
          <CardWrapper>
            <Link to={`/svg-component`} target={'_blank'}>컴포넌트형 SVG</Link>
          </CardWrapper>
          <CardWrapper>
            <h1>hi</h1>
          </CardWrapper>
        </CardContainer>
        <CardContainer>
          <CardWrapper>
            <h1>hi</h1>
          </CardWrapper>
          <CardWrapper>
            <h1>hi</h1>
          </CardWrapper>
          <CardWrapper>
            <h1>hi</h1>
          </CardWrapper>
        </CardContainer>
        {/* <SvgImg /> */}
        {/* <Calendar /> */}
      </Body>
    </>
  )
}